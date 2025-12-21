"""
Gift Scheduler - Monitors and delivers gifts at scheduled times
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Set
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import asyncio
from collections import defaultdict

logger = logging.getLogger(__name__)


class GiftScheduler:
    """Scheduler for monitoring and delivering gifts at scheduled times"""
    
    def __init__(self, supabase_client):
        """
        Initialize the gift scheduler
        
        Args:
            supabase_client: Supabase client instance
        """
        self.supabase = supabase_client
        self.scheduler = AsyncIOScheduler()
        self.delivered_gifts: Set[str] = set()  # Track delivered gift IDs
        self.sse_clients: Dict[str, List[asyncio.Queue]] = defaultdict(list)  # user_id -> queues
        self.running = False
        
        logger.info("✅ Gift Scheduler initialized")
    
    def start(self):
        """Start the scheduler"""
        if not self.running:
            # Check for gifts to deliver every 30 seconds
            self.scheduler.add_job(
                self.check_and_deliver_gifts,
                trigger=IntervalTrigger(seconds=30),
                id='gift_delivery_check',
                name='Check and deliver scheduled gifts',
                replace_existing=True
            )
            
            self.scheduler.start()
            self.running = True
            logger.info("✅ Gift Scheduler started - checking every 30 seconds")
    
    def stop(self):
        """Stop the scheduler"""
        if self.running:
            self.scheduler.shutdown(wait=False)
            self.running = False
            logger.info("✅ Gift Scheduler stopped")
    
    async def check_and_deliver_gifts(self):
        """
        Check for gifts that need to be delivered and push notifications to recipients
        """
        try:
            logger.info("🔍 Checking for gifts to deliver...")
            
            if not self.supabase:
                logger.warning("⚠️ Supabase client not available")
                return
            
            # Get current time
            now = datetime.now(timezone.utc)
            now_str = now.isoformat()
            
            # Query gifts that:
            # 1. Have delivery_time <= now
            # 2. Status is 'completed' (gift is ready)
            # 3. Haven't been delivered yet (not in delivered_gifts set)
            # 4. Not checked yet (checked = false or null)
            
            response = self.supabase.table("gifts").select("*").eq("status", "completed").lte("delivery_time", now_str).execute()
            
            if not response.data:
                logger.info("📭 No gifts ready for delivery")
                return
            
            gifts_to_deliver = []
            for gift in response.data:
                gift_id = gift.get("id")
                checked = gift.get("checked", False)
                
                # Skip if already delivered or already checked
                if gift_id in self.delivered_gifts or checked:
                    continue
                
                gifts_to_deliver.append(gift)
            
            if not gifts_to_deliver:
                logger.info("📭 No new gifts to deliver (all already delivered or checked)")
                return
            
            logger.info(f"🎁 Found {len(gifts_to_deliver)} gift(s) ready for delivery")
            
            # Deliver each gift
            for gift in gifts_to_deliver:
                await self.deliver_gift(gift)
            
        except Exception as e:
            logger.error(f"❌ Error checking gifts: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
    
    async def deliver_gift(self, gift: Dict[str, Any]):
        """
        Deliver a gift by pushing notification to recipient
        
        Args:
            gift: Gift data
        """
        try:
            gift_id = gift.get("id")
            to_user_id = gift.get("to_user_id")
            delivery_email = gift.get("delivery_email")
            
            logger.info(f"🎁 Delivering gift {gift_id} to user {to_user_id} / email {delivery_email}")
            
            # Mark as delivered in memory
            self.delivered_gifts.add(gift_id)
            
            # Push notification to recipient via SSE
            notification_data = {
                "type": "gift_delivered",
                "gift": gift,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # If recipient has a user_id, send to their SSE connection
            if to_user_id and to_user_id in self.sse_clients:
                await self.push_notification(to_user_id, notification_data)
                logger.info(f"✅ Gift {gift_id} notification sent to user {to_user_id} via SSE")
            else:
                # If no SSE connection, the notification will be picked up when user logs in
                # and the NotificationComponent fetches gifts
                logger.info(f"📝 Gift {gift_id} queued for user {to_user_id} (no active SSE connection)")
            
            # Optionally: Send email notification
            # await self.send_email_notification(gift)
            
        except Exception as e:
            logger.error(f"❌ Error delivering gift {gift_id}: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
    
    async def push_notification(self, user_id: str, notification_data: Dict[str, Any]):
        """
        Push notification to all SSE clients of a user
        
        Args:
            user_id: User ID
            notification_data: Notification data to send
        """
        if user_id not in self.sse_clients:
            logger.warning(f"⚠️ No SSE clients for user {user_id}")
            return
        
        clients = self.sse_clients[user_id]
        disconnected_clients = []
        
        for queue in clients:
            try:
                await queue.put(notification_data)
                logger.info(f"✅ Notification pushed to SSE client queue for user {user_id}")
            except Exception as e:
                logger.error(f"❌ Error pushing to SSE client: {e}")
                disconnected_clients.append(queue)
        
        # Remove disconnected clients
        for queue in disconnected_clients:
            clients.remove(queue)
    
    def register_sse_client(self, user_id: str, queue: asyncio.Queue):
        """
        Register an SSE client for a user
        
        Args:
            user_id: User ID
            queue: AsyncIO queue for sending notifications
        """
        self.sse_clients[user_id].append(queue)
        logger.info(f"✅ SSE client registered for user {user_id} (total: {len(self.sse_clients[user_id])})")
    
    def unregister_sse_client(self, user_id: str, queue: asyncio.Queue):
        """
        Unregister an SSE client for a user
        
        Args:
            user_id: User ID
            queue: AsyncIO queue to remove
        """
        if user_id in self.sse_clients and queue in self.sse_clients[user_id]:
            self.sse_clients[user_id].remove(queue)
            logger.info(f"✅ SSE client unregistered for user {user_id} (remaining: {len(self.sse_clients[user_id])})")
            
            # Clean up empty user entries
            if len(self.sse_clients[user_id]) == 0:
                del self.sse_clients[user_id]
                logger.info(f"✅ Removed empty SSE client list for user {user_id}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get scheduler statistics"""
        return {
            "running": self.running,
            "delivered_gifts_count": len(self.delivered_gifts),
            "active_sse_connections": sum(len(clients) for clients in self.sse_clients.values()),
            "unique_users_connected": len(self.sse_clients)
        }

