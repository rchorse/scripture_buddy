import 'dart:async';

/// Raised when an Amplify auth call does not come back.
///
/// Amplify's web worker can wedge — most reliably after a sign-out, but we have
/// seen sign-up hang too — and when it does the future never completes and never
/// throws. Left alone the UI sits on "Signing in…" or "Creating…" forever, which
/// is indistinguishable from a slow network and gives the reader nothing to do.
class AuthTimeout implements Exception {
  const AuthTimeout(this.message);
  final String message;
  @override
  String toString() => message;
}

/// Fails an auth call that hangs, so the UI can offer a way out.
///
/// The limit is generous on purpose: a cold Lambda behind a paused Aurora is
/// legitimately slow, and turning a slow success into an error would be worse
/// than the hang it replaces.
Future<T> guardAuth<T>(
  Future<T> call, {
  Duration limit = const Duration(seconds: 25),
  String what = 'That',
}) =>
    call.timeout(
      limit,
      onTimeout: () => throw AuthTimeout(
        '$what took too long. Reload the page and try again.',
      ),
    );
