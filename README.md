# 🚀 Automated Opportunity Finder

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Python](https://img.shields.io/badge/Python-3.x-green.svg)
![JavaScript](https://img.shields.io/badge/JavaScript-Vanilla-yellow.svg)

An open-source, fully automated tracking dashboard that hunts for **Remote Jobs**, **Research Assistant (RA) Positions**, and **Government Funds** in the background, updating a live Glassmorphism dashboard entirely on its own!

## ✨ Features

- **💼 Smart Job Fetching:** Automatically curates remote tech jobs (Flutter, Machine Learning, Python, etc.) from **WeWorkRemotely** and **Remotive**, filtering out senior/staff positions to focus on solo developers and juniors.
- **🎓 Professor & RA Finder:** Scans global research databases (EuropePMC) for recently published papers in Deep Learning, VLSI, and LLMs. It directly extracts **100% verified emails** of the professors, giving you immediate contact points for PhD/RA prospects.
- **🇧🇩 BD Govt Tracker:** Automatically monitors Bangladesh Govt (ICT Division & BCC) notice boards for new scholarships, fellowships, and startup grants.
- **🤖 Zero Maintenance (Auto Git Push):** The Python backend runs every 30 minutes. If it finds a new opportunity or detects a closed one, it automatically executes `git add`, `git commit`, and `git push`, keeping your GitHub Pages dashboard permanently live and updated!
- **🎨 Premium UI:** Built with Vanilla CSS utilizing modern Glassmorphism, neon glows, and smooth staggered micro-animations.

## 🛠️ Tech Stack
- **Backend:** Python 3 (`requests`, `beautifulsoup4`, `xml.etree`)
- **Database:** Local JSON (`jobs_database.json`)
- **Frontend:** HTML5, CSS3, Vanilla JavaScript
- **Hosting:** GitHub Pages

## 🚀 How to Run Locally

If you want to run this tool on your own machine to track jobs or customize keywords:

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/jobfinder.git
   cd jobfinder
   ```

2. **Install Python Dependencies:**
   ```bash
   pip install requests beautifulsoup4 urllib3
   ```

3. **Configure Keywords (Optional):**
   Open `opportunity_finder.py` and modify the `KEYWORDS` and `EXCLUDE_WORDS` arrays to match your specific tech stack and interests.

4. **Run the Tracker:**
   ```bash
   python3 opportunity_finder.py
   ```
   The script will start running in the background and check for updates every 30 minutes.

5. **View the Dashboard:**
   Open `index.html` in your browser to view the beautifully rendered data!

## 🤝 How to Contribute

Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1. **Fork the Project**
2. **Create your Feature Branch** (`git checkout -b feature/AmazingFeature`)
3. **Commit your Changes** (`git commit -m 'Add some AmazingFeature'`)
4. **Push to the Branch** (`git push origin feature/AmazingFeature`)
5. **Open a Pull Request**

### Ideas for Contribution:
- Add a new scraping source for jobs (e.g., Himalayas, RemoteOK API).
- Add support for Telegram/Discord Webhooks for instant notifications.
- Improve the CSS animations or add a Light/Dark theme toggle.

## 📜 License
Distributed under the MIT License. See `LICENSE` for more information.

---
*Built with ❤️ for solo developers and researchers.*
