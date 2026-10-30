# Frames

Every PNG in this folder becomes a campaign on the GitHub Pages site.

1. Upload `my-campaign.png` here (GitHub: **Add file → Upload files**). The file name becomes the URL: `/c/my-campaign/`.
   - Must be PNG with a transparent area where the photo shows through.
   - 400–4000 px per side, square (e.g. 1080×1080) recommended, ≤ 10 MB.
2. Optional: add `my-campaign.json` next to it:
   ```json
   { "title": "My Campaign", "description": "Why people should add this frame." }
   ```
   Without it, the title is derived from the file name.
3. Commit to `main`. The **Deploy to GitHub Pages** workflow validates the frame and publishes it within a minute or two.

To remove a campaign, delete its PNG (and JSON).
