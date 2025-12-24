# Installation Guide

## Quick Start (5 minutes)

### 1. Install Core Dependencies

```bash
cd drawtopia-backend
pip install -r requirements.txt
```

This installs all required packages including:
- FastAPI, Uvicorn (web framework)
- Security packages (slowapi, pyjwt, cryptography, bleach, itsdangerous)
- Supabase, Google Gemini, OpenAI clients
- Image processing (Pillow)
- PDF generation (reportlab)
- Audio generation (gtts)

### 2. Configure Environment

```bash
# Copy the template
cp env.example .env

# Edit with your values
nano .env  # or use your preferred editor
```

**Minimum required configuration:**
```bash
# API Keys
GEMINI_API_KEY=your_gemini_api_key
OPENAI_API_KEY=your_openai_api_key

# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_KEY=your_supabase_service_key

# Security (generate random strings)
JWT_SECRET=your-secure-random-string
CSRF_SECRET_KEY=your-secure-random-string
ENCRYPTION_PASSWORD=your-secure-password
ENCRYPTION_SALT=your-secure-salt
```

**Generate secure random strings:**
```bash
python -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(32))"
python -c "import secrets; print('CSRF_SECRET_KEY=' + secrets.token_urlsafe(32))"
python -c "import secrets; print('ENCRYPTION_PASSWORD=' + secrets.token_urlsafe(32))"
python -c "import secrets; print('ENCRYPTION_SALT=' + secrets.token_urlsafe(16))"
```

### 3. Run the Application

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Visit: http://localhost:8000/docs for API documentation

## Optional: Enhanced Virus Scanning

By default, the system uses **basic security checks** for file uploads:
- File size validation
- Extension checking
- Executable signature detection
- Embedded script detection

For **enhanced virus scanning** with ClamAV:

### Install ClamAV

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install clamav clamav-daemon
sudo systemctl start clamav-daemon
sudo systemctl enable clamav-daemon

# Update virus definitions
sudo freshclam
```

**macOS:**
```bash
brew install clamav
brew services start clamav

# Update virus definitions
freshclam
```

**Windows:**
Download from: https://www.clamav.net/downloads

### Install Python ClamAV Client

```bash
pip install clamd
```

### Verify Installation

```bash
python -c "import clamd; cd = clamd.ClamdUnixSocket(); print('ClamAV Status:', cd.ping())"
```

If successful, you'll see: `ClamAV Status: PONG`

## Verification

### 1. Check Health Endpoint

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "gemini_client_initialized": true,
  "supabase_configured": true,
  "virus_scanner_available": true,  // false if ClamAV not installed
  "security": {
    "rate_limiting": "enabled",
    "csrf_protection": "enabled",
    "virus_scanning": "enabled"  // or "basic_checks_only"
  }
}
```

### 2. Test Security Features

```bash
# Test rate limiting
for i in {1..150}; do curl http://localhost:8000/health; done
# Should get 429 (Too Many Requests) after limit

# Get CSRF token
curl http://localhost:8000/api/csrf-token

# Test CSRF protection
curl -X POST http://localhost:8000/api/books/generate -d '{}'
# Should get 403 (Forbidden) without CSRF token
```

## Troubleshooting

### Issue: Import errors

**Solution**: Make sure you're in the correct directory and virtual environment
```bash
cd drawtopia-backend
pip install -r requirements.txt
```

### Issue: "clamd not installed" warning

**This is normal!** The system works with basic security checks by default.

To enable enhanced scanning, follow the "Optional: Enhanced Virus Scanning" section above.

### Issue: "ClamAV daemon not available"

**Options:**
1. **Use basic checks** (default) - No action needed
2. **Install ClamAV** - Follow installation steps above
3. **Verify ClamAV is running**:
   ```bash
   # Linux
   sudo systemctl status clamav-daemon
   
   # macOS
   brew services list | grep clamav
   ```

### Issue: Port 8000 already in use

**Solution**: Use a different port
```bash
uvicorn main:app --port 8001
```

### Issue: Environment variables not loading

**Solution**: Ensure .env file exists and is in the correct location
```bash
ls -la .env
# Should show the .env file

# Check if variables are loaded
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print('JWT_SECRET:', os.getenv('JWT_SECRET'))"
```

## Production Deployment

### Additional Steps for Production

1. **Set production environment:**
```bash
ENVIRONMENT=production
ALLOWED_ORIGINS=https://yourdomain.com
ALLOWED_HOSTS=yourdomain.com,api.yourdomain.com
```

2. **Use production WSGI server:**
```bash
pip install gunicorn

gunicorn main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

3. **Set up reverse proxy (Nginx):**
```nginx
server {
    listen 80;
    server_name api.yourdomain.com;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

4. **Enable HTTPS:**
```bash
sudo certbot --nginx -d api.yourdomain.com
```

## Docker Deployment (Optional)

Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y clamav clamav-daemon && \
    apt-get clean

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Optional: Install clamd for enhanced scanning
RUN pip install clamd

# Copy application
COPY . .

# Start ClamAV and application
CMD freshclam && \
    clamd && \
    uvicorn main:app --host 0.0.0.0 --port 8000
```

Build and run:
```bash
docker build -t drawtopia-backend .
docker run -p 8000:8000 --env-file .env drawtopia-backend
```

## Next Steps

1. ✅ Installation complete
2. ⏭️ Review [Security Documentation](SECURITY_README.md)
3. ⏭️ Configure Supabase (see [JWT Configuration](SUPABASE_JWT_CONFIG.md))
4. ⏭️ Run database migrations
5. ⏭️ Test all endpoints
6. ⏭️ Deploy to production

## Support

- **Documentation**: See [SECURITY_README.md](SECURITY_README.md)
- **Quick Reference**: See [SECURITY_QUICK_REFERENCE.md](SECURITY_QUICK_REFERENCE.md)
- **Issues**: Create a GitHub issue

---

**Installation Guide Version**: 1.0.0  
**Last Updated**: 2024-12-24

