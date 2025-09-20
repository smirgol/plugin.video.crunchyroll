# Crunchyroll plugin for Kodi

Crunchyroll a KODI (XBMC) plugin for Crunchyroll.com

This is a fork of the original repository by MrKrabat: https://github.com/MrKrabat/plugin.video.crunchyroll

> [!WARNING]
> You need an active Crunchyroll account in order to use this plugin!

--- 

### What this plugin currently can do:

- [x] Supports all Crunchyroll regions
- [x] Login with your account
- [x] Search for anime
- [x] Browse all popular anime
- [x] Browse all simulcast seasons
- [x] Browse all updated anime
- [x] Browse all anime alphabetically
- [x] Browse all genres
- [x] Browse all seasons
- [x] Browse all resumable episodes/movies
- [x] View queue/playlist
- [x] View history
- [x] View all seasons/arcs of an anime
- [x] View all episodes of and season/arc
- [x] Context menu "Goto series" and "Goto season"
- [x] Add anime to your queue/playlist
- [x] Display various information
- [x] Watch videos with premium subscription
- [x] Synchronizes playback stats with Crunchyroll
- [x] Optionally soft-subs only
- [x] Configure up to two languages for subtitles / dubs
- [x] Crunchylists support
- [x] Crunchyroll profiles

### What it currently can't do:

- [ ] View random anime
- [ ] Remove anime from your queue/playlist
- [ ] Browse all featured anime
- [ ] Browse all new anime
- [ ] Mark as watched from context menu and sync that to crunchyroll

***

### How to install

You can either manually download the plugin, or use the repository.

#### Repository (recommended)

Download Repository: [Crunchyroll Repo](https://raw.githubusercontent.com/smirgol/crunchyroll_repo/refs/heads/main/repository.smirgol/repository.smirgol-1.0.1.zip)

Installation:

- Download ZIP file
- Put ZIP file onto your KODI System
- Go to Addon Settings and do a "Install from ZIP file"
- Pick the downloaded file and install
- Go back to the Addon Settings overview page
- Go to "Install from repository"
- Scroll down to "smirgols repository" and open it
- Install the Crunchyroll app
- If you have installed the addon manually before:
  - Confirm the first warning with YES - this will overwrite the manual installation
  - Confirm the second warning with NO - these will keep your settings
- You should be ready to go, open the crunchyroll app as usual

#### Manual installation

There are two types for each kodi version:

**Stable:** Use this if you prefer a stable and more or less tested version.

**Staging:** Use this if you would like to receive any updates as soon as possible.

| Kodi version  | Stable                                                                                        | Staging                                                                                               |
|---------------|-----------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------|
| Omega / Nexus | [Download](https://github.com/smirgol/plugin.video.crunchyroll/archive/refs/heads/main.zip)   | [Download](https://github.com/smirgol/plugin.video.crunchyroll/archive/refs/heads/nexus-staging.zip)  |
| Matrix        | [Download](https://github.com/smirgol/plugin.video.crunchyroll/archive/refs/heads/matrix.zip) | [Download](https://github.com/smirgol/plugin.video.crunchyroll/archive/refs/heads/matrix-staging.zip) |
| Leia          | [Download](https://github.com/smirgol/plugin.video.crunchyroll/archive/refs/heads/leia.zip)   | [Download](https://github.com/smirgol/plugin.video.crunchyroll/archive/refs/heads/leia-staging.zip)   |


> [!NOTE]
> *Leia* is discontinued, it will no longer receive new features. But I'll try to keep it alive as long as possible.

***

### Authentication

This plugin uses **Device Authentication** for secure login to your Crunchyroll account.

#### First Setup
1. Open the Crunchyroll plugin in Kodi
2. A dialog will appear with a **device code** and **activation URL**
3. On your phone/computer, visit the displayed URL (e.g., `https://www.crunchyroll.com/activate`)
4. Enter the **device code** shown in Kodi
5. Sign in with your Crunchyroll account
6. Return to Kodi - authentication will complete automatically

#### Re-authentication
- Authentication tokens are automatically refreshed
- If re-authentication is needed, the device code dialog will appear again
- Simply repeat the activation process

> [!TIP]
> Keep the Kodi dialog open while activating on your device. The code expires after a few minutes.

***

### Troubleshooting

#### Authentication Issues
- **"Device code expired"**: Close the dialog and try again to get a new code
- **"Authentication cancelled"**: The activation was cancelled on the website - restart the process
- **Connection errors**: Check your internet connection and try again
- **Still having issues?**: Enable debug logging and create an issue:
  1. Go to Kodi Settings → Add-ons → My add-ons → Video add-ons → Crunchyroll → Configure
  2. Navigate to "Developer Options" → Enable "Debug Logging"
  3. Try to reproduce the problem
  4. Create an issue on [GitHub](https://github.com/smirgol/plugin.video.crunchyroll/issues) with the Kodi log file

#### General Issues
- **Videos won't play**: Ensure you have an active Crunchyroll Premium subscription
- **Missing subtitles**: Check subtitle language settings in the addon configuration
- **Performance issues**: Enable/disable "Soft Subtitles" setting to improve playback

***

### Supported Languages

* English
* German
* Portuguese
* Spanish
* French

***

### Recent Changes

#### Version 2.0.0+ (Device Authentication Update)
- **🔐 New Authentication System**: Switched from email/password to secure device authentication
- **📱 Device Code Flow**: Authenticate using your phone/computer browser
- **🔄 Automatic Token Refresh**: No more manual re-login required
- **🌐 Better CloudFlare Support**: Improved compatibility with Crunchyroll's protection
- **🌍 Enhanced Translations**: All user-facing messages now properly translated
- **⚡ Performance Improvements**: Optimized proxy handling and resource management
- **🛡️ Improved Security**: No more storing passwords in Kodi settings

> [!IMPORTANT]
> **Breaking Change**: Email/password authentication is no longer supported. Existing users will be migrated to device authentication automatically on next login.

***

### Contributors

* MrKrabat
* smirgol
* lumiru
* rjousse18
* Corubba
* Gonzalo1987
* robofunk
* xLAva
* TheFantasticLoki
* Nux007
* vlfr1979
* davidkna
* jasonfrancis
* APachecoDiSanti
* Acidzero2020
* ...and all the forgotten heroes :)

***

### Disclaimer

_This website and addon is not affiliated with Crunchyroll._

_Kodi® (formerly known as XBMC™) is a registered trademark of the XBMC Foundation.
This website and addon is not affiliated with Kodi, Team Kodi, or the XBMC Foundation._