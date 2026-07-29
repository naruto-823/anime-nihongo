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

登录令牌存入 iOS Keychain / Android Keystore 对应的 Expo SecureStore，不写入普通本地存储。
