#!/usr/bin/env python3
"""
Email Listener - Monitors Gmail inbox for new emails and triggers webhook.
Simpler than IMAP IDLE, works with all email providers.

Run this separately: python scripts/email_listener.py
"""
import asyncio
import logging
import aiohttp
import imaplib
import email
from datetime import datetime, timezone
import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

WEBHOOK_URL = "http://localhost:8000/api/v1/webhook/email-arrived"
WEBHOOK_TOKEN = settings.WEBHOOK_TOKEN
POLL_INTERVAL = 10  # Check every 10 seconds (faster than background worker's 60)


class EmailListener:
    def __init__(self):
        self.imap = None
        self.last_checked_uid = None
        self.running = False

    def connect(self):
        """Connect to IMAP server."""
        logger.info(f"Connecting to {settings.IMAP_HOST}:{settings.IMAP_PORT}")
        try:
            self.imap = imaplib.IMAP4_SSL(settings.IMAP_HOST, settings.IMAP_PORT)
            self.imap.login(settings.IMAP_USER, settings.IMAP_PASSWORD)
            logger.info("✓ Connected to IMAP")
            return True
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False

    def select_inbox(self):
        """Select INBOX folder and get last UID."""
        try:
            self.imap.select("INBOX")
            
            # Get all message UIDs
            status, data = self.imap.uid("search", None, "ALL")
            if data and data[0]:
                uids = data[0].split()
                self.last_checked_uid = int(uids[-1]) if uids else 0
                logger.info(f"Starting from UID: {self.last_checked_uid}")
            else:
                self.last_checked_uid = 0
                logger.info("Inbox is empty, starting from UID: 0")
        except Exception as e:
            logger.error(f"Error selecting inbox: {e}")
            self.last_checked_uid = 0

    async def check_new_emails(self):
        """Check for new emails and process them."""
        try:
            # Search for emails after last checked UID
            search_criteria = f"UID {self.last_checked_uid}:*"
            status, data = self.imap.uid("search", None, search_criteria)
            
            if not data or not data[0]:
                return 0
            
            new_uids = data[0].split()
            if not new_uids:
                return 0
            
            # Update last checked UID
            max_uid = int(new_uids[-1])
            if max_uid > self.last_checked_uid:
                logger.info(f"Found {len(new_uids)} new email(s)")
                
                # Process each new email
                processed_count = 0
                for uid in new_uids:
                    if int(uid) > self.last_checked_uid:
                        if await self.process_email(uid):
                            processed_count += 1
                
                self.last_checked_uid = max_uid
                return processed_count
            
            return 0
        
        except Exception as e:
            logger.error(f"Error checking emails: {e}")
            return 0

    async def process_email(self, uid):
        """Process a single email and call webhook."""
        try:
            status, msg_data = self.imap.uid("FETCH", uid, "(RFC822)")
            if not msg_data or not msg_data[0]:
                return False
            
            email_body = msg_data[0][1]
            msg = email.message_from_bytes(email_body)
            
            # Extract email data
            sender = msg.get("From", "").split("<")[-1].rstrip(">")
            subject = msg.get("Subject", "")
            to = msg.get("To", "")
            body = ""
            attachments = []
            
            logger.info(f"Processing email from {sender}: {subject}")
            
            # Extract body and attachments
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if content_type == "text/plain":
                        try:
                            body = part.get_payload(decode=True).decode()
                        except:
                            body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    elif part.get_content_disposition() == "attachment":
                        attachments.append({
                            "filename": part.get_filename() or "attachment",
                            "content_type": content_type,
                            "size": len(part.get_payload()),
                        })
            else:
                try:
                    body = msg.get_payload(decode=True).decode()
                except:
                    body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
            
            logger.info(f"  From: {sender}")
            logger.info(f"  Subject: {subject}")
            logger.info(f"  Attachments: {len(attachments)}")
            
            # Call webhook
            return await self._call_webhook(
                sender=sender,
                to=to,
                subject=subject,
                body=body,
                attachments=attachments,
            )
        
        except Exception as e:
            logger.error(f"Error processing email {uid}: {e}")
            return False

    async def _call_webhook(self, sender, to, subject, body, attachments):
        """POST email to webhook."""
        payload = {
            "sender": sender,
            "to": to,
            "subject": subject,
            "body": body,
            "attachments": attachments,
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "X-Webhook-Token": WEBHOOK_TOKEN,
                    "Content-Type": "application/json",
                }
                
                async with session.post(WEBHOOK_URL, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        logger.info(f"✓ Webhook triggered successfully for '{subject}'")
                        return True
                    else:
                        error_text = await resp.text()
                        logger.error(f"✗ Webhook failed: {resp.status} - {error_text}")
                        return False
        
        except asyncio.TimeoutError:
            logger.error("Webhook request timed out")
            return False
        except Exception as e:
            logger.error(f"Error calling webhook: {e}")
            return False

    async def run(self):
        """Main loop - check for emails periodically."""
        self.running = True
        logger.info(f"Email listener started (checking every {POLL_INTERVAL}s)")
        logger.info("Listening for new emails...")
        
        check_count = 0
        while self.running:
            try:
                processed = await self.check_new_emails()
                check_count += 1
                
                if check_count % 6 == 0:  # Log every 60 seconds
                    logger.info(f"Listening... (checked {check_count} times, {processed} total processed)")
                
                await asyncio.sleep(POLL_INTERVAL)
            
            except KeyboardInterrupt:
                logger.info("Stopping listener (Ctrl+C pressed)...")
                self.running = False
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(POLL_INTERVAL)

    def stop(self):
        """Stop the listener."""
        self.running = False
        if self.imap:
            try:
                self.imap.close()
                self.imap.logout()
            except:
                pass


async def main():
    """Entry point."""
    listener = EmailListener()
    
    if not listener.connect():
        logger.error("Failed to connect to IMAP server")
        return
    
    listener.select_inbox()
    
    try:
        await listener.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        listener.stop()


if __name__ == "__main__":
    asyncio.run(main())
