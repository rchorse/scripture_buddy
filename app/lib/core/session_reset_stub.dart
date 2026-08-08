/// Mobile and desktop keep a healthy Amplify after sign-out, so there is
/// nothing to reset — the caller just navigates back to the sign-in screen.
Future<bool> resetAfterSignOut() async => false;
