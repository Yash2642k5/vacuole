# 🛍️ Vacuole : A Telegram-based Intelligent Shopping Agent

This is an intelligent, agentic AI-powered shopping assistant that helps users search for the **best products across top e-commerce platforms**, directly through **Telegram** – no need for a website or app download.

---

## 🔍 Features

- 🧠 **Agentic Workflow**: Uses AI agents to understand user queries and automate product discovery.
- 📦 **Product Scraping**: Real-time scraping from e-commerce sites (e.g., Flipkart, Amazon, Meesho).
- 💬 **Telegram Bot Interface**: Chat-based frontend where users interact directly with the bot.
- 💾 **User History Tracking**: Remembers user preferences and queries for improved future suggestions.
- 🧩 **Product Details**: Returns product title, price, image, specs, and direct purchase link.
- 🖼️ **Card UI on Telegram**: Clean product cards with inline buttons.
- 🔒 **No App Required**: Works entirely through Telegram + browser automation — simple and frictionless UX.

---

## 🛠️ Tech Stack

- **Python**
- **Playwright** for headless browser scraping
- **LangGraph / Langchain agents** for orchestrating workflows
- **Firebase Firestore** for user history and logging
- **Telegram Bot API**
- **Docker** for deployment (currently, may change in future)
- **dotenv** for environment variable management

---

## 🚀 How It Works

1. **User sends a message** (e.g., “Best budget phone under ₹15,000”) to the Telegram bot.
2. The **agent parses** the intent and triggers the scraper.
3. The scraper visits websites like **Flipkart**, performs the search, and extracts:
   - Product title
   - Specs (e.g., RAM, Storage, Display)
   - Price
   - Image
   - Buy link
4. The result is **ranked**, formatted, and sent back in the Telegram chat.

---

## 🧪 Supported Websites

1. ✅ **Default**: Flipkart.com  
2. 🔜 Coming Soon: Amazon, Meesho, Croma, TataCliq  
   > (Optional: Mention the site name in your query to target it specifically)

---

## 📦 Installation

### 1. Clone the Repo
```bash
git clone https://github.com/Yash25/vacuole.git
cd vacuole

---
### 2. Installing Dependencies
```bash
pip install -r requirements.txt

---
### 3. Set up Environmental variable in .env
```bash
GAMINI_API_KEY = "put you key here (For complex task)"
FIREBASE_CREDENTIALS = "put your database credentials here (for storing and managing the user-chats)"
GROQ_API_KEY = "put your api key here (for Simple task)"

---
### 4. Run Locally
```bash
python telebot.py


---
🧑‍💻 Contributors :
Yash Sinha – Creator & manages the frontend flow (Telegram input/output)
Ayush Garg – Creator & manages the browser automation and scraping workflow