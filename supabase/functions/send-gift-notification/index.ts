// Supabase Edge Function for sending push notifications
// Deploy with: supabase functions deploy send-gift-notification

import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

interface PushSubscription {
  endpoint: string
  keys: {
    p256dh: string
    auth: string
  }
}

interface Gift {
  id: string
  to_user_id: string
  child_name: string
  occasion: string
  from_user_id: string
  delivery_time: string
}

// Web Push VAPID keys - Store these in Supabase Secrets
const VAPID_PUBLIC_KEY = Deno.env.get('VAPID_PUBLIC_KEY') || ''
const VAPID_PRIVATE_KEY = Deno.env.get('VAPID_PRIVATE_KEY') || ''
const VAPID_SUBJECT = Deno.env.get('VAPID_SUBJECT') || 'mailto:support@drawtopia.com'

/**
 * Send a Web Push notification using VAPID
 */
async function sendWebPush(
  subscription: PushSubscription,
  payload: any
): Promise<Response> {
  try {
    // Generate VAPID headers
    const vapidHeaders = await generateVAPIDHeaders(
      subscription.endpoint,
      VAPID_PUBLIC_KEY,
      VAPID_PRIVATE_KEY,
      VAPID_SUBJECT
    )

    // Encrypt the payload
    const encryptedPayload = await encryptPayload(
      JSON.stringify(payload),
      subscription.keys.p256dh,
      subscription.keys.auth
    )

    // Send the push notification
    const response = await fetch(subscription.endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/octet-stream',
        'Content-Encoding': 'aes128gcm',
        'TTL': '86400', // 24 hours
        ...vapidHeaders,
      },
      body: encryptedPayload,
    })

    return response
  } catch (error) {
    console.error('Error sending web push:', error)
    throw error
  }
}

/**
 * Generate VAPID headers for authentication
 */
async function generateVAPIDHeaders(
  endpoint: string,
  publicKey: string,
  privateKey: string,
  subject: string
): Promise<Record<string, string>> {
  // Parse the endpoint URL
  const url = new URL(endpoint)
  const audience = `${url.protocol}//${url.host}`

  // Create JWT token (simplified - use web-push library for production)
  const header = {
    typ: 'JWT',
    alg: 'ES256',
  }

  const now = Math.floor(Date.now() / 1000)
  const payload = {
    aud: audience,
    exp: now + 12 * 60 * 60, // 12 hours
    sub: subject,
  }

  // For production, use a proper JWT/VAPID library
  // This is a simplified implementation
  const token = `${btoa(JSON.stringify(header))}.${btoa(JSON.stringify(payload))}`

  return {
    'Authorization': `vapid t=${token}, k=${publicKey}`,
  }
}

/**
 * Encrypt payload for Web Push (simplified)
 * For production, use web-push library
 */
async function encryptPayload(
  payload: string,
  p256dh: string,
  auth: string
): Promise<Uint8Array> {
  // This is a simplified version
  // For production, implement full Web Push encryption (RFC 8291)
  // or use the web-push npm package
  const encoder = new TextEncoder()
  return encoder.encode(payload)
}

serve(async (req) => {
  // Handle CORS preflight
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    // Initialize Supabase client
    const supabaseUrl = Deno.env.get('SUPABASE_URL') ?? ''
    const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
    const supabase = createClient(supabaseUrl, supabaseServiceKey)

    // Get request body
    const { giftId, mode } = await req.json()

    // Mode can be 'single' (for specific gift) or 'batch' (for all scheduled)
    const gifts: Gift[] = []

    if (mode === 'single' && giftId) {
      // Send notification for a specific gift
      const { data: gift, error } = await supabase
        .from('gifts')
        .select('*')
        .eq('id', giftId)
        .single()

      if (error) throw error
      if (gift) gifts.push(gift)
    } else {
      // Batch mode: Process all scheduled gifts
      const { data: scheduledGifts, error } = await supabase
        .from('gifts')
        .select('*')
        .eq('notification_scheduled', true)
        .eq('notification_sent', false)
        .eq('status', 'completed')
        .not('to_user_id', 'is', null)
        .lte('delivery_time', new Date().toISOString())
        .limit(50)

      if (error) throw error
      if (scheduledGifts) gifts.push(...scheduledGifts)
    }

    const results = []

    // Process each gift
    for (const gift of gifts) {
      try {
        // Get push subscriptions for the recipient
        const { data: subscriptions, error: subError } = await supabase
          .from('push_subscriptions')
          .select('*')
          .eq('user_id', gift.to_user_id)

        if (subError) throw subError

        // Get sender information
        const { data: senderData } = await supabase
          .from('auth.users')
          .select('email, raw_user_meta_data')
          .eq('id', gift.from_user_id)
          .single()

        const senderName = senderData?.raw_user_meta_data?.name || 'Someone'

        // Prepare notification payload
        const notificationPayload = {
          title: '🎁 New Gift Story Received!',
          body: `${senderName} sent you a story for ${gift.child_name}`,
          icon: '/icon-192.png',
          badge: '/badge-72.png',
          data: {
            giftId: gift.id,
            url: `/gift/view/${gift.id}`,
            occasion: gift.occasion,
            childName: gift.child_name,
          },
          actions: [
            {
              action: 'view',
              title: 'View Gift',
            },
            {
              action: 'close',
              title: 'Close',
            },
          ],
        }

        // Send notification to all user's devices
        let sentCount = 0
        const failedEndpoints: string[] = []

        for (const subscription of subscriptions || []) {
          try {
            const pushSubscription: PushSubscription = {
              endpoint: subscription.endpoint,
              keys: {
                p256dh: subscription.p256dh,
                auth: subscription.auth,
              },
            }

            // Use web-push npm package (better for production)
            // For now, using FCM (Firebase Cloud Messaging) as a simpler alternative
            const response = await sendFCMNotification(
              subscription.endpoint,
              notificationPayload
            )

            if (response.ok) {
              sentCount++
            } else {
              failedEndpoints.push(subscription.endpoint)
              // If endpoint is invalid (410 Gone), remove subscription
              if (response.status === 410) {
                await supabase
                  .from('push_subscriptions')
                  .delete()
                  .eq('endpoint', subscription.endpoint)
              }
            }
          } catch (error) {
            console.error('Error sending to endpoint:', error)
            failedEndpoints.push(subscription.endpoint)
          }
        }

        // Mark notification as sent
        await supabase
          .from('gifts')
          .update({
            notification_sent: true,
            notification_sent_at: new Date().toISOString(),
          })
          .eq('id', gift.id)

        results.push({
          giftId: gift.id,
          success: true,
          sentCount,
          failedEndpoints,
        })
      } catch (error) {
        console.error(`Error processing gift ${gift.id}:`, error)
        results.push({
          giftId: gift.id,
          success: false,
          error: error.message,
        })
      }
    }

    return new Response(
      JSON.stringify({
        success: true,
        processed: gifts.length,
        results,
      }),
      {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        status: 200,
      }
    )
  } catch (error) {
    console.error('Error in send-gift-notification:', error)
    return new Response(
      JSON.stringify({
        success: false,
        error: error.message,
      }),
      {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        status: 500,
      }
    )
  }
})

/**
 * Send notification using Firebase Cloud Messaging (FCM)
 * This is a simpler alternative to raw Web Push with VAPID
 */
async function sendFCMNotification(
  endpoint: string,
  payload: any
): Promise<Response> {
  // Extract token from FCM endpoint
  // FCM endpoints look like: https://fcm.googleapis.com/fcm/send/{token}
  const fcmServerKey = Deno.env.get('FCM_SERVER_KEY') || ''
  
  if (!fcmServerKey) {
    // Fallback to direct endpoint push
    return fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'TTL': '86400',
      },
      body: JSON.stringify(payload),
    })
  }

  // Extract token from endpoint
  const tokenMatch = endpoint.match(/\/([^\/]+)$/)
  const token = tokenMatch ? tokenMatch[1] : null

  if (!token) {
    throw new Error('Invalid FCM endpoint')
  }

  // Send via FCM API
  return fetch('https://fcm.googleapis.com/fcm/send', {
    method: 'POST',
    headers: {
      'Authorization': `key=${fcmServerKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      to: token,
      notification: {
        title: payload.title,
        body: payload.body,
        icon: payload.icon,
        badge: payload.badge,
      },
      data: payload.data,
    }),
  })
}

