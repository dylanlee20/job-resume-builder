# Quick Start Guide - NewWhale Career v2

## 🚀 Get Running in 5 Minutes

### Step 1: Get OpenAI API Key
1. Go to https://platform.openai.com/api-keys
2. Click "Create new secret key"
3. Copy the key (starts with `sk-...`)

### Step 2: Configure Environment
```bash
cd ~/Desktop/job-tracker-v2
nano .env
```

Update these lines:
```bash
OPENAI_API_KEY=sk-your-actual-key-here  # REQUIRED for resume assessment
```

Save and exit (Ctrl+O, Enter, Ctrl+X)

### Step 3: Run the App
```bash
# Activate virtual environment
source venv/bin/activate

# Run app
python app.py
```

### Step 4: Access the App
Open browser: http://localhost:5002

### Step 5: Test It
1. **Register**: Click "Register" → Create account (free tier)
2. **Upload**: Go to "Resume Upload" → Select PDF/DOCX
3. **Assess**: Click "Get Free Assessment" → Wait ~10 seconds
4. **View**: See your score, strengths, weaknesses, industry fit!

---

## 🔧 Troubleshooting

### "Module not found" error
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### "OpenAI API error"
- Check your API key in `.env`
- Ensure you have credits in your OpenAI account

### "File too large" error
- Resume must be under 10MB
- Try compressing your PDF

### Database errors
```bash
# Reset database
rm data/jobs.db
python app.py  # Will recreate tables
```

---

## 👤 Default Admin Login
- Username: `admin`
- Password: `newwhale2024`

(Change this in production!)

---

## 📝 What Works Now
✅ User registration & login  
✅ Resume upload (PDF/DOCX)  
✅ Resume parsing  
✅ AI-powered assessment  
✅ Rate limiting (3/day free)  
✅ Assessment history  

## 🚧 Coming Soon
⏳ Stripe payments  
⏳ Premium subscription  
⏳ Resume revision (premium)  
⏳ Job listings  
⏳ Admin dashboard  

---

## 🎯 Next Steps After Testing

1. **If you like it:** Proceed with Stripe integration (Phase 4)
2. **Need changes:** Let me know what to adjust
3. **Want to deploy:** We'll set up VPS in Phase 7

See `PROGRESS_REPORT.md` for detailed status!
