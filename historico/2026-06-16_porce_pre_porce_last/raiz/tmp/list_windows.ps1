$code = @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

public class WinEnum {
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumWindowsProc cb, IntPtr p);
    [DllImport("user32.dll")] static extern int GetWindowTextLength(IntPtr hWnd);
    [DllImport("user32.dll")] static extern int GetWindowText(IntPtr hWnd, StringBuilder sb, int max);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr hWnd, out RECT r);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
    delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    public static List<string> List() {
        var result = new List<string>();
        EnumWindows((h, p) => {
            if (!IsWindowVisible(h)) return true;
            int len = GetWindowTextLength(h);
            if (len == 0) return true;
            var sb = new StringBuilder(len + 1);
            GetWindowText(h, sb, sb.Capacity);
            RECT r; GetWindowRect(h, out r);
            result.Add(sb.ToString() + " | " + (r.R - r.L) + "x" + (r.B - r.T));
            return true;
        }, IntPtr.Zero);
        return result;
    }
}
'@
Add-Type -TypeDefinition $code
[WinEnum]::List() | Set-Content 'D:\Deep-AeroTwin-UE57-Test\tmp\windows_list.txt'
