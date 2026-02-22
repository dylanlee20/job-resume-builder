"""
Lightweight GitHub webhook listener for auto-deploy.
Runs on port 9000 and triggers deploy.sh on push to master.
"""

import hashlib
import hmac
import json
import os
import subprocess
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/newwhale-webhook.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

WEBHOOK_SECRET = os.environ.get('GITHUB_WEBHOOK_SECRET', '')
DEPLOY_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'deploy.sh')
DEPLOY_BRANCH = 'master'


def verify_signature(payload_body, signature_header):
    """Verify GitHub webhook signature (HMAC-SHA256)"""
    if not WEBHOOK_SECRET:
        logger.warning("No GITHUB_WEBHOOK_SECRET set — skipping signature verification")
        return True
    if not signature_header:
        return False
    expected = 'sha256=' + hmac.new(
        WEBHOOK_SECRET.encode(), payload_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != '/webhook':
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get('Content-Length', 0))
        payload_body = self.rfile.read(content_length)
        signature = self.headers.get('X-Hub-Signature-256', '')

        if not verify_signature(payload_body, signature):
            logger.warning("Invalid webhook signature — rejecting")
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b'Invalid signature')
            return

        try:
            payload = json.loads(payload_body)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        event = self.headers.get('X-GitHub-Event', '')
        ref = payload.get('ref', '')

        if event == 'push' and ref == f'refs/heads/{DEPLOY_BRANCH}':
            logger.info(f"Push to {DEPLOY_BRANCH} detected — deploying...")
            try:
                result = subprocess.run(
                    ['bash', DEPLOY_SCRIPT],
                    capture_output=True, text=True, timeout=120
                )
                logger.info(f"Deploy stdout: {result.stdout}")
                if result.returncode != 0:
                    logger.error(f"Deploy stderr: {result.stderr}")
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'Deployed')
            except Exception as e:
                logger.error(f"Deploy failed: {e}")
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f'Deploy error: {e}'.encode())
        else:
            logger.info(f"Ignoring event={event} ref={ref}")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'Ignored')

    def do_GET(self):
        """Health check"""
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Webhook listener running')

    def log_message(self, format, *args):
        """Suppress default HTTP logging (we use our own logger)"""
        pass


if __name__ == '__main__':
    port = int(os.environ.get('WEBHOOK_PORT', 9000))
    server = HTTPServer(('0.0.0.0', port), WebhookHandler)
    logger.info(f"Webhook server listening on port {port}")
    server.serve_forever()
