# 修炼塔原生应用

这是一套基于 Expo + React Native 的 iOS/Android 共用代码，直接连接现有的 FastAPI 与 PostgreSQL 服务。

## 本地运行

```bash
npm ci
npm start
```

随后可以用 Expo Go 扫码，或按 `i`/`a` 在 iOS 模拟器、Android 模拟器中启动。

默认 API 地址为 `https://api.narutoooo.com`。开发环境可覆盖：

```bash
EXPO_PUBLIC_API_BASE=http://localhost:8000 npm start
```

## 构建检查

```bash
npm run typecheck
npm run export:ios
npm run export:android
```

生产签名包使用 EAS Build：

```bash
npx eas-cli build --platform all --profile production
```

在尚未配置 Expo/EAS 账号时，GitHub Actions 的 `Build native preview`
工作流会为每次合入 `main` 的原生改动自动生成可安装的 Android 调试 APK。
构建成功后可在该次 Action 的 Artifacts 区域下载
`anime-nihongo-android-preview-*`。

iOS 真机包必须使用 Apple Developer 签名，无法用无账号的调试证书替代。

登录令牌存入 iOS Keychain / Android Keystore 对应的 Expo SecureStore，不写入普通本地存储。
