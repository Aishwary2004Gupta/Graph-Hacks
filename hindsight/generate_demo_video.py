import os
import time
import subprocess
from playwright.sync_api import sync_playwright

VIDEO_DIR = os.path.abspath("demo_video_temp")
OUTPUT_MP4 = os.path.abspath(os.path.join("demo_assets", "hindsight_demo.mp4"))
os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(os.path.dirname(OUTPUT_MP4), exist_ok=True)

print("Starting Playwright Chrome with video recording...")
with sync_playwright() as p:
    browser = p.chromium.launch(
        channel="chrome",
        headless=True,
        args=["--no-sandbox", "--disable-setuid-sandbox", "--window-size=1920,1080"]
    )
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        record_video_dir=VIDEO_DIR,
        record_video_size={"width": 1920, "height": 1080}
    )
    page = context.new_page()

    # Step 1: Open app
    print("Navigating to http://localhost:8000...")
    page.goto("http://localhost:8000", wait_until="networkidle")
    page.wait_for_timeout(3500)

    # Step 2: Investigation (Root Cause & Blast Radius)
    print("Demonstrating Investigation: Postgres Outage...")
    page.click("text=🚨 Postgres Outage Suspects")
    page.wait_for_timeout(800)
    page.click("button:has-text('⚡ Investigate Query')")
    page.wait_for_timeout(3500)

    # Scroll the answer container
    print("Scrolling answer container...")
    ans_box = page.locator("#ans")
    ans_box.evaluate("el => el.scrollTo({ top: 220, behavior: 'smooth' })")
    page.wait_for_timeout(2000)
    ans_box.evaluate("el => el.scrollTo({ top: 500, behavior: 'smooth' })")
    page.wait_for_timeout(2000)
    ans_box.evaluate("el => el.scrollTo({ top: 0, behavior: 'smooth' })")
    page.wait_for_timeout(1500)

    # Show Cypher audit trail
    print("Inspecting Cypher audit trail...")
    page.evaluate("document.querySelector('#trace').scrollIntoView({ behavior: 'smooth' })")
    page.wait_for_timeout(1500)
    page.click("details.trace-item summary")
    page.wait_for_timeout(2000)
    page.evaluate("window.scrollTo({ top: 0, behavior: 'smooth' })")
    page.wait_for_timeout(1500)

    # Step 3: Company Brain (Kafka Architecture Decisions)
    print("Demonstrating Company Brain: Kafka Architecture...")
    page.click("text=🏛️ Kafka Architecture Decisions")
    page.wait_for_timeout(800)
    page.click("button:has-text('⚡ Investigate Query')")
    page.wait_for_timeout(3000)
    ans_box.evaluate("el => el.scrollTo({ top: 180, behavior: 'smooth' })")
    page.wait_for_timeout(2000)

    # Step 4: Graph Algorithm (PageRank)
    print("Demonstrating PageRank Criticality...")
    page.click("text=📊 Critical Services (PageRank)")
    page.wait_for_timeout(800)
    page.click("button:has-text('⚡ Investigate Query')")
    page.wait_for_timeout(3000)

    # Step 5: Multi-Agent Swarm (Triage -> Investigator -> Scribe)
    print("Demonstrating Autonomous Multi-Agent Swarm...")
    page.click("button:has-text('🤖 Run Autonomous Swarm')")
    page.wait_for_timeout(4500)

    # View Swarm Handoffs tab
    print("Viewing Swarm Handoffs tab...")
    page.click("button:has-text('Swarm Handoffs')")
    page.wait_for_timeout(3000)

    # Step 6: Memory Deck (Semantic Fact Learning)
    print("Demonstrating Agent Memory Deck...")
    page.click("button:has-text('Agent Memory Deck')")
    page.wait_for_timeout(2000)
    page.fill("#mem-subj", "redis-cache")
    page.wait_for_timeout(400)
    page.fill("#mem-attr", "lead_oncall")
    page.wait_for_timeout(400)
    page.fill("#mem-val", "Asha")
    page.wait_for_timeout(600)
    page.click("button:has-text('Commit Fact')")
    page.wait_for_timeout(3500)

    # Step 7: Final View on Knowledge Graph
    print("Switching back to Knowledge Graph...")
    page.click("button:has-text('Knowledge Graph (FalkorDB)')")
    page.wait_for_timeout(1000)
    page.click("button:has-text('Fit')")
    page.wait_for_timeout(3500)

    # Close to flush video recording
    video_path = page.video.path()
    print("Recorded raw video to:", video_path)
    context.close()
    browser.close()

# Convert to high-quality MP4 using ffmpeg
print(f"Converting raw video to high-definition MP4: {OUTPUT_MP4}...")
ffmpeg_cmd = [
    r"C:\PATH_Programs\ffmpeg.exe",
    "-y",
    "-i", video_path,
    "-c:v", "libx264",
    "-preset", "medium",
    "-crf", "22",
    "-pix_fmt", "yuv420p",
    OUTPUT_MP4
]

res = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
if res.returncode == 0:
    size_mb = os.path.getsize(OUTPUT_MP4) / (1024 * 1024)
    print(f"SUCCESS! MP4 video created successfully at:\n{OUTPUT_MP4} ({size_mb:.2f} MB)")
else:
    print("FFmpeg error:", res.stderr)
