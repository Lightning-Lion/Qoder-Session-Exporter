# 导出Qoder App聊天记录

> 导出的是Qoder App的聊天记录，不是qodercli的聊天记录。

> 导出的是静态的HTML文件，供将聊天记录分享给别人，而不是原始数据或JSON。


- #### 以远程调试模式打开Qoder App

```bash
/Applications/Qoder.app/Contents/MacOS/Electron --remote-debugging-port=9222
```

- 在AI聊天标题上右键“在新窗口打开”，调整窗口的尺寸到屏幕的一半。

- 打开网页调试工具（`edge://inspect/#devices`），对于最上面的这个名为`about:blank`的点击“Inspect”按钮。

- 先运行`expand-disclosure.js`，然后运行`expandAll();removeAllConstraints()`，然后运行`export-session.js`，然后保存到合适的位置，最后运行`python fix-font.py <HTML文件路径>`，最后运行`chmod +x serve.sh`然后`./serve.sh`。