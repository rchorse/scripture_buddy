library;

/// Restarting the app after sign-out. See [resetAfterSignOut] for why.
export 'session_reset_stub.dart'
    if (dart.library.js_interop) 'session_reset_web.dart';
