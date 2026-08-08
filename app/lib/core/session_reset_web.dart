import 'package:web/web.dart' as web;

/// Reloads the page after sign-out.
///
/// On web, `Amplify.Auth.signIn` hangs forever — no network request is ever
/// made — if `signOut` ran earlier in the same page session. Amplify's auth
/// worker does not survive the sign-out, and the next sign-in waits on a
/// channel nobody answers. Reproduced repeatedly: sign out, sign in, hang;
/// reload, sign in, works.
///
/// A reload is the only reliable way to get a working Amplify back, so
/// sign-out ends the page rather than returning to the sign-in screen inside
/// a session that can no longer sign anyone in.
Future<bool> resetAfterSignOut() async {
  web.window.location.reload();
  return true;
}
