// Battery & System Dashboard - ตัวเปิดโปรแกรม (แทน launch.vbs) · ลุงพี
//   BatteryDashboard.exe            เริ่ม server.ps1 (ถ้ายังไม่ทำงาน) แล้วเปิดหน้าแดชบอร์ดใน Edge แบบแอป
//   BatteryDashboard.exe --server   เริ่มเฉพาะ server ไม่เปิดหน้าต่าง (ใช้ตอนเปิดเครื่อง)
// server.ps1 ต้องอยู่โฟลเดอร์เดียวกับ exe นี้
using System;
using System.Diagnostics;
using System.IO;
using System.Net.Sockets;
using System.Threading;
using System.Windows.Forms;

static class BatteryDashboard {
  const int Port = 8765;
  const string Url = "http://localhost:8765/";

  static bool ServerUp() {
    try {
      using (var c = new TcpClient()) {
        var r = c.BeginConnect("127.0.0.1", Port, null, null);
        return r.AsyncWaitHandle.WaitOne(500) && c.Connected;
      }
    } catch { return false; }
  }

  [STAThread]
  static int Main(string[] args) {
    string dir = AppDomain.CurrentDomain.BaseDirectory;
    string server = Path.Combine(dir, "server.ps1");
    bool serverOnly = args.Length > 0 && args[0].Equals("--server", StringComparison.OrdinalIgnoreCase);

    if (!ServerUp()) {
      if (!File.Exists(server)) {
        MessageBox.Show("ไม่พบไฟล์ " + server, "Battery & System Dashboard", MessageBoxButtons.OK, MessageBoxIcon.Error);
        return 1;
      }
      var psi = new ProcessStartInfo("powershell.exe",
        "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -NonInteractive -File \"" + server + "\"");
      psi.UseShellExecute = false; psi.CreateNoWindow = true; psi.WorkingDirectory = dir;
      Process.Start(psi);
      // รอ server พร้อม (ปกติ 2-4 วินาที) สูงสุด 20 วินาที
      for (int i = 0; i < 40 && !ServerUp(); i++) Thread.Sleep(500);
    }
    if (serverOnly) return 0;

    string edge = null;
    foreach (var env in new[] { "ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA" }) {
      string root = Environment.GetEnvironmentVariable(env);
      if (string.IsNullOrEmpty(root)) continue;
      string p = Path.Combine(root, @"Microsoft\Edge\Application\msedge.exe");
      if (File.Exists(p)) { edge = p; break; }
    }
    if (edge != null) Process.Start(edge, "--app=" + Url + " --window-size=1000,700");
    else Process.Start(Url);
    return 0;
  }
}
