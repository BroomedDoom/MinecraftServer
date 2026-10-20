# BlockHost

BlockHost is a simple Windows app for running a Minecraft Java server and sharing it with friends through [playit.gg](https://playit.gg/). You do not need to change router settings or open a port.

This guide is written for someone downloading this project from GitHub for the first time. BlockHost currently supports **Windows** and **Vanilla Minecraft Java servers**.


# NOTE: For easiest install, run the release BlockHost-Setup.exe

## What you need

- A Windows 10 or 11 computer that can stay on while people play.
- An internet connection.
- A free [playit.gg account](https://playit.gg/).
- Python 3.10 or newer and Java installed. Java must support the Minecraft version you choose.
- The Windows playit agent. Download it from the [official playit agent releases](https://github.com/playit-cloud/playit-agent/releases/latest). Choose the Windows x64 file (`playit-windows-x86_64.exe`).

## To Connect the Playit Agent to your account

The first time BlockHost starts the playit agent, look in the app's console for a Playit claim link or code.

1. Open the claim link in a browser. If only a code is shown, follow the link or instructions printed with it.
2. Sign in to your playit.gg account (or create one).
3. Approve the request to add/claim the agent. Give it a name you will recognize, such as `My Home PC`.
4. Return to BlockHost. The agent should now appear online on the playit.gg website.

If you do not see a claim link, confirm that the playit executable setting points to `playit.exe`, save settings, and choose **Restart**. Check the app console again.

## Create your Minecraft tunnel on playit.gg

Do this on the [playit.gg website](https://playit.gg/), while signed in to the same account that claimed the agent:

1. Open **Tunnels** in your playit.gg dashboard and choose **Create Tunnel** or **Add Tunnel**.
2. Choose the **Minecraft Java** tunnel type/preset.
3. Select the agent you just claimed.
4. Set the local/origin address to `127.0.0.1` and the local/origin port to `25565`.
5. Create/save the tunnel. If the website asks you to choose a public address or region, choose an available option.
6. Open the new tunnel on the website and note its public address (hostname) and port. It will look similar to `example.playit.gg:12345`. Your address and port will be different.

The local port must match the Minecraft server port. BlockHost's default is `25565`. If you change **server-port** in **Server properties**, use that same port in the playit tunnel and restart the server.

## Let friends join

Make sure BlockHost shows the Minecraft server and Playit tunnel as running. Send friends the public address and port shown on the playit.gg tunnel page (or in BlockHost's **Public address** panel(although this panel sometimes does not work)). They can join from **Minecraft: Java Edition** using **Multiplayer → Direct Connection** or **Add Server**.

The server computer must stay on, and both the Minecraft server and playit agent must be running for friends to connect. Use **Stop** in BlockHost when you want to shut them down.

## If something does not work

- **The server does not start:** run **Set up server**, check that Java is installed and selected, and read the latest messages in the console. On first start, accept the EULA in BlockHost.
- **Playit has no address:** confirm the agent is claimed and online on the website, then confirm a Minecraft Java tunnel exists for that agent. Restart BlockHost after changing settings.
- **Friends cannot connect:** make sure both status cards say running, the tunnel's local port matches **Server properties → server-port** (usually `25565`), and you sent the tunnel's public address including its port.
- **The address says unknown host:** check the address spelling and try again after a short wait. The playit address is shown on the tunnel page.

## Keep your server safe

- Never share your playit claim link/code, account password, or private server files publicly.
- The server folder contains your world and player data. Back it up before moving or replacing it.
- `config.json`, your server folder, and `.host-token` are excluded from Git by this project. Do not remove those exclusions to publish your personal settings, world, or local token.


## Project status

BlockHost currently supports Vanilla Minecraft setup, server start/stop/restart, console commands, basic server settings, and Playit address display. Paper and richer tunnel-status features are not included yet. Minecraft EULA acceptance is always a choice you make yourself.
