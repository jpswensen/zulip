# Direct mobile push notifications (custom-signed apps)

This document explains how to make a self-hosted Zulip server deliver
iOS (APNs) and/or Android (FCM) push notifications **directly** to a
mobile app you build and sign yourself, bypassing the [Zulip mobile
push notification service](mobile-push-notifications.md) (sometimes
called "the bouncer").

:::{warning}
This is **not** the recommended path for most operators. Apple's and
Google's security models do not let a self-hosted server send
notifications to the official Zulip apps from the App Store / Play
Store; that is exactly the problem the [hosted
service](mobile-push-notifications.md) solves, and it is free for most
self-hosters. Going direct means **building, signing, and distributing
your own mobile app**, and taking on responsibility for your own APNs /
FCM credentials. Read [the standard
documentation](mobile-push-notifications.md) before choosing this path.
:::

It is intended for situations like a small server for family, friends,
or a team, where you are willing to maintain a custom build of the
mobile app and hold your own push credentials.

## Why direct delivery requires a custom app

A push notification is delivered to the device by the OS vendor's push
service — Apple's **APNs** for iOS, Google's **FCM** for Android.
Neither vendor accepts a push from an arbitrary server. Each requires:

- Credentials **scoped to a specific app bundle ID / package name**
  (for APNs, an auth key or certificate tied to your Apple Developer
  team; for FCM, a Firebase service account).
- A **device token** that the vendor issued to that exact app on that
  exact device, which the app must have previously sent to your server.

The official Zulip iOS app's bundle ID (`org.zulip.Zulip`) belongs to
Zulip's Apple Developer team, so only Zulip's credentials can push to
it — which is why the official apps must use the hosted service. To
deliver directly, you must ship an app whose bundle ID **you** control
and for which **you** hold the matching APNs/FCM credentials. The Zulip
server performs no check on the bundle ID; whether a given push is
authorized is enforced by Apple/Google against your credentials.

## The three delivery paths

1. **Legacy direct delivery** (what this document uses). Your server
   holds APNs/FCM credentials and contacts Apple/Google directly. The
   app registers its device token via the legacy endpoints
   [`apns_device_token`](https://zulip.com/api/add-apns-token) and
   [`android_gcm_reg_id`](https://zulip.com/api/add-fcm-token), and the
   token is stored in the server's `PushDeviceToken` table.
2. **Hosted-service delivery.** The server proxies notifications
   through Zulip's service, which holds the credentials for the
   official apps' bundle IDs. Enabled by
   `ZULIP_SERVICE_PUSH_NOTIFICATIONS = True`.
3. **End-to-end-encrypted (E2EE) delivery.** A newer path in which the
   service forwards notifications without seeing their plaintext. **It
   requires the hosted service**: registration
   (`register_push_device`) encrypts the device token with the
   service's public key, and on a server with no service configured the
   endpoint raises `PushServiceNotConfiguredError` ("Server is not
   configured to use push notification service."). There is no
   "direct E2EE" mode.

Because E2EE registration cannot complete on a direct server, your
custom app must use the **legacy** registration endpoints. The server
advertises which mode it is in through the `push_notifications_direct`
boolean on
[`GET /server_settings`](https://zulip.com/api/get-server-settings), so a
self-hosted-aware build can choose the legacy path automatically.

## What you need

- A self-hosted Zulip server you administer, running a build that
  supports single-platform direct delivery (see [Differences from
  upstream](#differences-from-upstream-zulip)).
- For iOS: an [Apple Developer Program](https://developer.apple.com/programs/)
  membership (US$99/year).
- For Android: a [Firebase](https://console.firebase.google.com/)
  project (free).
- A toolchain to build the Zulip mobile app (Xcode + CocoaPods for iOS;
  Android Studio for Android), and a **bundle ID / package name you
  own** — for example `com.example.zulip`. It must not be
  `org.zulip.Zulip`.

The examples below use the placeholders `com.example.zulip` (bundle
ID), `TEAMID1234` (Apple Team ID), `ABCDE12345` (APNs Key ID), and
`zulip.example.com` (your server). Substitute your own values.

## Apple (APNs) setup

### 1. Register an App ID

In the [Apple Developer portal](https://developer.apple.com/account/),
under **Certificates, Identifiers & Profiles → Identifiers**, register
an App ID for your bundle ID (`com.example.zulip`) with the **Push
Notifications** capability enabled. Note your **Team ID** (shown at the
top right of the portal).

### 2. Create an APNs auth key (recommended)

You can authenticate to APNs two ways; token-based auth is preferred
because one key works for any app in your team and does not expire:

- **Token-based (`.p8`)** — under **Keys → +**, enable **Apple Push
  Notifications service (APNs)**, create the key, and download the
  `.p8`. **You can only download it once** — back it up securely. Note
  the 10-character **Key ID**.
- **Certificate-based (`.pem`)** — a per-app push SSL certificate that
  expires yearly. Use only if you cannot use a key.

### 3. Install the credentials and configure the server

Copy the key to your server with restrictive permissions:

```bash
sudo install -o root -g zulip -m 0640 \
    AuthKey_ABCDE12345.p8 /etc/zulip/apns/AuthKey_ABCDE12345.p8
```

In `/etc/zulip/settings.py`, leave `ZULIP_SERVICE_PUSH_NOTIFICATIONS`
unset and add:

```python
APNS_TOKEN_KEY_FILE = "/etc/zulip/apns/AuthKey_ABCDE12345.p8"
APNS_TOKEN_KEY_ID = "ABCDE12345"
APNS_TEAM_ID = "TEAMID1234"
# True targets Apple's sandbox gateway (Xcode debug builds only);
# set False for TestFlight / Ad Hoc / App Store builds. Default: True.
APNS_SANDBOX = False
```

(For certificate-based auth, set `APNS_CERT_FILE` instead of the three
`APNS_TOKEN_*`/`APNS_TEAM_ID` settings.)

Restart the server to apply the change:

```bash
sudo su zulip -c '/home/zulip/deployments/current/scripts/restart-server'
```

### 4. Build and distribute a custom iOS app

Direct delivery needs an app you sign with your own team and bundle ID:

- In the app's Xcode project, set the **Bundle Identifier** to
  `com.example.zulip`, the **Signing Team** to your Apple Developer
  team, and enable the **Push Notifications** capability and
  **Background Modes → Remote notifications**.
- The app must register through the legacy endpoint when the server
  reports `push_notifications_direct: true`. It sends the APNs device
  token as `token` and the bundle ID as `appid`; the server stores
  `appid` as the notification's APNs **topic**, so it must equal your
  bundle ID. A stock build that only knows the E2EE registration flow
  will fail on a direct server (see [the three
  paths](#the-three-delivery-paths)).
- Distribute to your users via **TestFlight** or an **Ad Hoc** /
  enterprise build.

:::{important}
**Sandbox vs production tokens must match on both sides.** An Xcode
**debug** build run from a cable gets a _sandbox_ APNs token and needs
`APNS_SANDBOX = True`. TestFlight / Ad Hoc / App Store builds get
_production_ tokens and need `APNS_SANDBOX = False`. A mismatch fails
with `BadDeviceToken`. This is the most common "I configured everything
and nothing arrives" problem.
:::

### 5. Verify end-to-end

First confirm the server reports the direct mode:

```bash
curl -s https://zulip.example.com/api/v1/server_settings \
    | python3 -m json.tool | grep -i push_notifications
```

You should see both `"push_notifications_enabled": true` and
`"push_notifications_direct": true`. If `_enabled` is false, the server
cannot read your credentials — recheck the file paths and that the
files are readable by the `zulip` user.

Then log into the custom app on a **real device** (APNs does not work
in the simulator) and confirm a token row was created:

```bash
sudo -u zulip /home/zulip/deployments/current/manage.py shell -c \
  "from zerver.models import PushDeviceToken; \
   [print(t.user_id, t.kind, t.ios_app_id, t.token[:8] + '...') \
    for t in PushDeviceToken.objects.all()]"
```

The `ios_app_id` should be your bundle ID. Now background the app and
have another user send a direct message; the banner should arrive
within a few seconds. If it doesn't, watch the logs:

```bash
sudo tail -F /var/log/zulip/errors.log /var/log/zulip/server.log \
  | grep -iE 'apns|push'
```

Common APNs errors:

- `BadDeviceToken` — the build's sandbox/production type does not match
  `APNS_SANDBOX`, or the token is stale.
- `BadTopic` — the app's bundle ID is not authorized by your APNs key
  (it must be an App ID in the same team).
- `Unregistered` — the app was uninstalled; the row is removed
  automatically on the next send.

## Android (FCM) setup

Android delivery is independent of iOS — configure it only if you also
ship a custom Android app. There is no sandbox/production split for FCM.

1. Create a [Firebase](https://console.firebase.google.com/) project
   and register an Android app for your package name (e.g.,
   `com.example.zulip`). This package name must match the
   `applicationId` in your custom Android build, and the Firebase
   client options compiled into the app must match this project.
2. Under **Project settings → Service accounts → Generate new private
   key**, download the service-account JSON and install it on the
   server:

   ```bash
   sudo install -o root -g zulip -m 0640 \
       firebase-adminsdk.json /etc/zulip/fcm-service-account.json
   ```

3. In `/etc/zulip/settings.py`:

   ```python
   ANDROID_FCM_CREDENTIALS_PATH = "/etc/zulip/fcm-service-account.json"
   ```

   Restart the server. The custom Android app registers its token via
   `POST /json/users/me/android_gcm_reg_id`, creating an FCM
   `PushDeviceToken` row.

The service-account JSON is the Android equivalent of your APNs key:
treat it as a production secret.

## Testing in a development environment first

Before configuring your production server, it is worth verifying the
full register-and-deliver loop in a [development
environment](../development/overview.md) against Apple's **sandbox**
gateway:

- Add the same `APNS_*` settings (with `APNS_SANDBOX = True`, since
  `flutter run` / Xcode produce debug/sandbox builds) to your dev
  settings, pointing `APNS_TOKEN_KEY_FILE` at a key stored outside
  version control (e.g., under `var/`, which is git-ignored).
- Expose the dev server to a physical phone over your LAN (set
  `EXTERNAL_HOST` to your machine's LAN IP) or via an HTTPS tunnel such
  as `ngrok`; `localhost` is not reachable from the device.
- Run the custom app as a debug build on a cabled device, log in, and
  send a test message while the app is backgrounded.

This isolates credential and app-build problems from production
server configuration.

## Operations, security, and gotchas

- **You now operate a push pipeline.** If your `.p8` key (or FCM
  service account) leaks, anyone holding it can push to any device that
  registered with your bundle ID. Treat these like TLS private keys,
  and back up the `.p8` (it is only downloadable once) alongside
  `/etc/zulip/`.
- **Configure only the platforms you ship.** The server advertises
  push as enabled whenever either platform's credentials are present.
  A user on a platform you have _not_ configured will see push as
  "enabled" but receive nothing (the send is a logged no-op), so do
  not tell users a platform is supported until you have shipped its
  app and credentials.
- **No usage limits or fees.** APNs and FCM do not bill for normal
  notification volume; there is no equivalent of the hosted service's
  free-tier ceiling.
- **No upstream support.** The Zulip project does not support this
  configuration; reproduce any official-app bug against the hosted
  service before reporting it.
- **Notification content.** Your server already composes its
  notifications, and in this mode it sends them to Apple/Google
  directly. Unlike the E2EE-via-service path, there is no third party
  in the delivery path at all.

## Differences from upstream Zulip

Direct single-platform delivery relies on these server behaviors:

- `sends_notifications_directly()` and `push_notifications_configured()`
  (`zerver/lib/push_notifications.py`) treat the server as configured
  for direct delivery when the hosted service is disabled and **either**
  APNs **or** FCM credentials are present (rather than requiring both),
  so you can ship to just one platform.
- [`GET /server_settings`](https://zulip.com/api/get-server-settings) returns
  `push_notifications_direct`, letting a custom-signed client choose the
  legacy registration endpoints over the service-only
  `register_push_device` flow.

Operators who use the standard hosted-service path are unaffected by
these changes.
