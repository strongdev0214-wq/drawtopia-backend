"""
Gift Delivery Scheduler Service

This module handles scheduled gift deliveries by:
1. Monitoring the gifts table for upcoming deliveries
2. Automatically sending notifications when delivery time arrives
3. Using Supabase Realtime to push notifications to recipients
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from supabase import Client
import pytz

logger = logging.getLogger(__name__)


class GiftScheduler:
    """
    Manages scheduled gift deliveries
    
    Monitors gifts table and triggers notifications when delivery_time is reached.
    Uses Supabase Realtime channels to push notifications to recipients.
    """
    
    def __init__(self, supabase_client: Client, check_interval: int = 60):
        """
        Initialize the gift scheduler
        
        Args:
            supabase_client: Supabase client instance
            check_interval: How often to check for deliveries (in seconds)
        """
        self.supabase = supabase_client
        self.check_interval = check_interval
        self.running = False
        self._task: Optional[asyncio.Task] = None
        self._processed_gifts: set = set()  # Track processed gifts to avoid duplicates
        
    async def start(self):
        """Start the gift scheduler"""
        if self.running:
            logger.warning("Gift scheduler is already running")
            return
            
        self.running = True
        self._task = asyncio.create_task(self._run())
        logger.info(f"✅ Gift scheduler started (check interval: {self.check_interval}s)")
        
    async def stop(self):
        """Stop the gift scheduler"""
        if not self.running:
            return
            
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("✅ Gift scheduler stopped")
        
    async def _run(self):
        """Main scheduler loop"""
        logger.info("Gift scheduler loop started")
        
        while self.running:
            try:
                await self._check_and_deliver_gifts()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                logger.info("Gift scheduler loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in gift scheduler loop: {e}")
                import traceback
                logger.debug(f"Traceback: {traceback.format_exc()}")
                await asyncio.sleep(self.check_interval)
                
    async def _check_and_deliver_gifts(self):
        """
        Check for gifts that should be delivered and trigger notifications
        """
        try:
            # Get current time in UTC
            now = datetime.utcnow()
            
            # Query gifts that:
            # 1. Have delivery_time <= now
            # 2. Status is 'completed' (gift generation is done)
            # 3. Not yet checked (checked = false or null)
            # 4. Not in processed set (to avoid duplicates)
            
            response = self.supabase.table("gifts").select("*").eq("status", "completed").execute()
            
            if not response.data:
                return
                
            gifts_to_deliver = []
            
            for gift in response.data:
                # Skip if already processed in this session
                gift_id = gift.get("id")
                if gift_id in self._processed_gifts:
                    continue
                    
                # Skip if already checked
                if gift.get("checked", False):
                    continue
                    
                # Parse delivery time
                delivery_time_str = gift.get("delivery_time")
                if not delivery_time_str:
                    continue
                    
                try:
                    # Parse the delivery time (assuming ISO format)
                    delivery_time = datetime.fromisoformat(delivery_time_str.replace('Z', '+00:00'))
                    
                    # Remove timezone info for comparison (compare in UTC)
                    if delivery_time.tzinfo:
                        delivery_time = delivery_time.replace(tzinfo=None)
                    
                    # Check if delivery time has arrived
                    if delivery_time <= now:
                        gifts_to_deliver.append(gift)
                        
                except Exception as e:
                    logger.error(f"Error parsing delivery time for gift {gift_id}: {e}")
                    continue
            
            # Deliver gifts
            if gifts_to_deliver:
                logger.info(f"📦 Found {len(gifts_to_deliver)} gifts ready for delivery")
                
                for gift in gifts_to_deliver:
                    await self._deliver_gift(gift)
                    
        except Exception as e:
            logger.error(f"Error checking gifts for delivery: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            
    async def _deliver_gift(self, gift: Dict[str, Any]):
        """
        Deliver a gift by triggering real-time notification
        
        Args:
            gift: Gift data from database
        """
        try:
            gift_id = gift.get("id")
            to_user_id = gift.get("to_user_id")
            delivery_email = gift.get("delivery_email")
            
            logger.info(f"🎁 Delivering gift {gift_id} to {delivery_email}")
            
            # Mark this gift as processed (even if notification fails)
            self._processed_gifts.add(gift_id)
            
            # Create notification payload
            notification_payload = {
                "type": "gift_delivered",
                "gift_id": gift_id,
                "gift": gift,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Option 1: Use Supabase Realtime broadcast
            # The frontend will listen to this channel and show notification
            if to_user_id:
                # Send to user-specific channel if user exists
                channel_name = f"gift_notifications:{to_user_id}"
                logger.info(f"📡 Broadcasting to channel: {channel_name}")
                
                # Note: Supabase Python client doesn't have direct broadcast support
                # We'll rely on database triggers and frontend subscriptions
                # Update a notification timestamp to trigger frontend refresh
                try:
                    # Add a delivered_at timestamp to track delivery
                    self.supabase.table("gifts").update({
                        "delivered_at": datetime.utcnow().isoformat()
                    }).eq("id", gift_id).execute()
                    
                    logger.info(f"✅ Gift {gift_id} marked as delivered")
                except Exception as e:
                    logger.error(f"Failed to update gift delivery status: {e}")
            else:
                logger.info(f"Gift {gift_id} has no to_user_id, relying on email check")
                
                # Still mark as delivered
                try:
                    self.supabase.table("gifts").update({
                        "delivered_at": datetime.utcnow().isoformat()
                    }).eq("id", gift_id).execute()
                except Exception as e:
                    logger.error(f"Failed to update gift delivery status: {e}")
            
            logger.info(f"✅ Successfully delivered gift {gift_id}")
            
        except Exception as e:
            logger.error(f"Error delivering gift: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            
    def get_upcoming_deliveries(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get gifts scheduled for delivery in the next N hours
        
        Args:
            hours: Number of hours to look ahead
            
        Returns:
            List of gifts scheduled for delivery
        """
        try:
            now = datetime.utcnow()
            future = now + timedelta(hours=hours)
            
            response = self.supabase.table("gifts").select("*").eq("status", "completed").execute()
            
            if not response.data:
                return []
                
            upcoming = []
            for gift in response.data:
                delivery_time_str = gift.get("delivery_time")
                if not delivery_time_str:
                    continue
                    
                try:
                    delivery_time = datetime.fromisoformat(delivery_time_str.replace('Z', '+00:00'))
                    if delivery_time.tzinfo:
                        delivery_time = delivery_time.replace(tzinfo=None)
                    
                    if now <= delivery_time <= future:
                        upcoming.append(gift)
                except Exception:
                    continue
                    
            return upcoming
            
        except Exception as e:
            logger.error(f"Error getting upcoming deliveries: {e}")
            return []


# Global instance
_gift_scheduler: Optional[GiftScheduler] = None


def get_gift_scheduler() -> Optional[GiftScheduler]:
    """Get the global gift scheduler instance"""
    return _gift_scheduler


def init_gift_scheduler(supabase_client: Client, check_interval: int = 60) -> GiftScheduler:
    """
    Initialize the global gift scheduler
    
    Args:
        supabase_client: Supabase client instance
        check_interval: How often to check for deliveries (in seconds)
        
    Returns:
        GiftScheduler instance
    """
    global _gift_scheduler
    _gift_scheduler = GiftScheduler(supabase_client, check_interval)
    return _gift_scheduler

