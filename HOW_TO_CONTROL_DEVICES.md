# How Jarvis controls other devices (and what it can't)

## The one rule
Jarvis can only touch the computer it is **running on**.
- Running in **Codespaces / the cloud** → it can open links in *your* browser (YouTube, Google, Maps, WhatsApp, calls) but cannot touch your PC, tablet or lights.
- Running on **your PC** (recommended) → it controls that PC, your Android tablet/phone (via ADB) and smart devices on your Wi-Fi.
  Your tablet then just opens Jarvis in its browser and acts as a remote.

## A. Control your PC (+ use the tablet as the remote)
1. On the PC: `pip install -r requirements.txt -r requirements-local.txt`
2. In `.env` set `JARVIS_LOCAL=1`   (or just run `start_on_pc.bat` / `./start_on_pc.sh`)
3. Start: `streamlit run Jarvis.py --server.address 0.0.0.0`
4. On the tablet open `http://<pc-ip>:8501` (the Device Control page shows the exact address).
5. Say or type: *open calculator · volume up · next song · lock my pc · open study hub · directions to Cubbon Park*
   - Safe actions run instantly. Lock, sleep, typing and power need a **Confirm** tap.
   - Shutdown/restart are OFF unless `JARVIS_ALLOW_POWER=1`.
   - Only allow-listed apps open (add yours in Device Control → My apps). Jarvis never runs free-form shell commands.
6. Microphone on a tablet needs HTTPS. Easiest: a private tunnel (Tailscale Serve or Cloudflare Tunnel) that gives you an https address.

## B. Control an Android tablet / phone (ADB)
1. Install *Android platform-tools* on the PC (adb must be in PATH, or set `ADB_PATH` in `.env`).
2. Tablet: Settings → About → tap *Build number* 7× → Developer options → **USB debugging** (or *Wireless debugging*).
3. Plug in USB and tap **Allow**  (Wi-Fi: Device Control → Android → enter `ip:5555` → Connect).
4. Say: *open YouTube on my tablet · tablet volume up · phone brightness 40 · turn wifi off on my tablet · screenshot on my tablet · send sms to +91… saying …*
   (SMS opens a drafted message - you tap Send.)
iPhone/iPad cannot be controlled this way (Apple does not allow it).

## C. Smart lights and devices (+ double-clap)
Device Control → **Smart devices & automations** → add a template:
- **Home Assistant**: Profile → Security → *Long-lived access token*. Use the "turn light ON" template, set your `light.xxx` entity and token.
- **Tasmota / Sonoff / Shelly plug**: use the plug template with the device IP.
- **IFTTT**: create a Webhooks applet, paste its trigger URL.
Then say *turn on the lights*. Control Panel → Voice → **Double-clap trigger** sends that same phrase when you clap twice.
The device must be reachable from where Jarvis runs (same Wi-Fi, or a cloud service like IFTTT).

## D. ElevenLabs voice (realistic Jarvis voice)
1. elevenlabs.io → Profile → **API Keys** → create a key (allow *Text to Speech* and *Voices: read*).
2. elevenlabs.io → Voices → pick a voice → copy its **Voice ID**.
3. Put both in `.env`:  `ELEVENLABS_API_KEY=...`  `ELEVENLABS_VOICE_ID=...`  (then Control Panel → API Keys → **Reload .env**)
4. Control Panel → Voice → **Test ElevenLabs now** - it shows the exact error if something is wrong.
   Free plans can only use *premade* voices / voices you created through the API.
5. Voice engine "Auto" uses ElevenLabs whenever a key exists. Control Panel → **Diagnostics** checks everything.

## E. If a link doesn't open
Browsers block pop-ups that aren't triggered by a tap. Jarvis tries to open the link; if the browser refuses, a big **Tap to open** button
appears at the bottom of the screen. In Chrome you can also allow pop-ups for the site (address bar icon).
