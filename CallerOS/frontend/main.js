const { app, BrowserWindow } = require('electron');
const path = require('path');

function createWindow() {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    title: "GoblinOS Workspace",
    backgroundColor: "#0B0E14",
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
    }
  });

  // Point to the local Python HTTP API / static web server
  win.loadURL('http://localhost:8080');

  // Open DevTools if running in development mode
  if (process.env.NODE_ENV === 'development') {
    win.webContents.openDevTools();
  }
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
