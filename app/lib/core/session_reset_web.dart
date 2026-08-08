import 'package:web/web.dart' as web;

/// Amplify's own IndexedDB database.
const _amplifyStore = 'com.amplify.awsCognitoAuthPlugin';

/// Clears Amplify's local auth state and reloads the page after sign-out.
///
/// On web, `Amplify.Auth.signIn` hangs after a `signOut` in the same browser:
/// it spawns its worker and then never issues a request, so the future neither
/// completes nor throws. A reload alone does not fix it, which means the wedge
/// is in what sign-out *persists*, not just in-memory worker state — so the
/// store has to go too.
///
/// The delete is requested before the reload rather than awaited: an open page
/// holds a connection and `deleteDatabase` blocks until it closes, so the
/// reload is what lets it complete.
///
/// Isolated by experiment: the same account with the same password signs in on
/// a fresh page load and hangs on the load that follows a sign-out.
Future<bool> resetAfterSignOut() async {
  try {
    web.window.indexedDB.deleteDatabase(_amplifyStore);
  } catch (_) {
    // Nothing to clear, or the browser refused — reload regardless.
  }
  web.window.location.reload();
  return true;
}

/// Exposed for the sign-in screen's last-resort retry.
void dropLocalAuthStore() {
  try {
    web.window.indexedDB.deleteDatabase(_amplifyStore);
  } catch (_) {
    // Best effort.
  }
}
