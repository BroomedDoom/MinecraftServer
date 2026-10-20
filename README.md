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

## 1. Download BlockHost

On this GitHub page, choose **Code**, then **Download ZIP**. Extract the ZIP to a folder you can find again, such as `Documents\BlockHost`.

If this project has a Windows installer under **Releases**, download and run `BlockHost-Setup.exe` instead. If there is no installer, use the source setup below.

### Set up the app from source

1. Install [Python for Windows](https://www.python.org/downloads/windows/) (3.10 or newer). During setup, check **Add Python to PATH**.
2. Install a Java runtime that supports your Minecraft version. The app needs Java to run the server.
3. Open the extracted `Minecraft Server App` folder.
4. In the folder address bar, type `powershell` and press Enter.
5. In the PowerShell window, run:

   ```powershell
   python main.py
   ```

## 2. Set the app's server and Playit files

In BlockHost, fill in the settings on the left:

1. **Server folder:** choose where BlockHost should keep your server and world. The default `server` folder inside the project is fine.
2. **Minecraft version:** leave it as `latest`, or enter a version you want to run.
3. **Memory (GB):** leave the default unless you know you need to change it.
4. **Java executable:** select the Java program on your computer if BlockHost has not found it automatically. It is usually named `java.exe` or `javaw.exe`, inside Java's `bin` folder.
5. **playit executable:** select the Windows playit agent you downloaded. If needed, rename the downloaded file to `playit.exe` so it is easy to find.
6. Choose **Save settings**.

Packaged versions may include Java and the playit agent already. If the app has filled in those settings, leave them as they are.

## 3. Set up the Minecraft server

1. Choose **Set up server** and wait for the download to finish.
2. Choose **Start**.
3. The first time you start, BlockHost shows the Minecraft EULA. Read it, open the linked EULA if you want, and check the agreement box only if you accept it. Choose **Accept and Start** to continue.
4. Wait for the console to show that the server has finished starting.

Keep BlockHost open while playing. Closing its window leaves the server running in the background. Open BlockHost again to check it or use **Stop** when you are done.

## 4. Connect the Playit agent to your account

The first time BlockHost starts the playit agent, look in the app's console for a Playit claim link or code.

1. Open the claim link in a browser. If only a code is shown, follow the link or instructions printed with it.
2. Sign in to your playit.gg account (or create one).
3. Approve the request to add/claim the agent. Give it a name you will recognize, such as `My Home PC`.
4. Return to BlockHost. The agent should now appear online on the playit.gg website.

If you do not see a claim link, confirm that the playit executable setting points to `playit.exe`, save settings, and choose **Restart**. Check the app console again.

## 5. Create your Minecraft tunnel on playit.gg

Do this on the [playit.gg website](https://playit.gg/), while signed in to the same account that claimed the agent:

1. Open **Tunnels** in your playit.gg dashboard and choose **Create Tunnel** or **Add Tunnel**.
2. Choose the **Minecraft Java** tunnel type/preset.
3. Select the agent you just claimed.
4. Set the local/origin address to `127.0.0.1` and the local/origin port to `25565`.
5. Create/save the tunnel. If the website asks you to choose a public address or region, choose an available option.
6. Open the new tunnel on the website and note its public address (hostname) and port. It will look similar to `example.playit.gg:12345`. Your address and port will be different.

The local port must match the Minecraft server port. BlockHost's default is `25565`. If you change **server-port** in **Server properties**, use that same port in the playit tunnel and restart the server.

## 6. Let friends join

Make sure BlockHost shows the Minecraft server and Playit tunnel as running. Send friends the public address and port shown on the playit.gg tunnel page (or in BlockHost's **Public address** panel). They can join from **Minecraft: Java Edition** using **Multiplayer → Direct Connection**.

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

## Build a Windows installer (optional)

To create an installer from source, install Python 3, Java is downloaded by the build script, and Inno Setup 6. In PowerShell, from the project folder, run:

```powershell
py -3 -m pip install -r requirements-build.txt
./build_windows.ps1
```

The installer will be created at `dist/BlockHost-Setup.exe`. The build downloads the Windows playit agent and Java runtime automatically.

## Project status

BlockHost currently supports Vanilla Minecraft setup, server start/stop/restart, console commands, basic server settings, and Playit address display. Paper and richer tunnel-status features are not included yet. Minecraft EULA acceptance is always a choice you make yourself.
