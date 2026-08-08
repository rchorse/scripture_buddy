import 'package:amplify_flutter/amplify_flutter.dart';
import 'package:flutter/material.dart';

import '../../core/session_reset.dart';
import '../reader/home_page.dart';
import 'age_gate_page.dart';
import 'onboarding_api.dart';
import 'sign_in_page.dart';

/// Decides the first screen: sign in, finish registering, or the app.
///
/// Restoring an existing session here is what lets the sign-in screen drop its
/// old `signOut()`-before-`signIn()` call. That call ran on every attempt, and
/// on web a sign-out leaves Amplify unable to sign in again until the page
/// reloads — which is why sign-in used to hang on "Signing in…" forever. See
/// `core/session_reset_web.dart`.
class AuthGate extends StatefulWidget {
  const AuthGate({super.key});

  @override
  State<AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<AuthGate> {
  final _api = OnboardingApi();
  late Future<Widget> _destination;

  @override
  void initState() {
    super.initState();
    _destination = _resolve();
  }

  Future<Widget> _resolve() async {
    try {
      final session = await Amplify.Auth.fetchAuthSession();
      if (!session.isSignedIn) return const SignInPage();
    } on Object {
      return const SignInPage();
    }

    try {
      final me = await _api.me();
      // /v1/me answers whatever the status, so an account that the rest of the
      // API refuses still reaches a screen that explains itself.
      if (me.status == 'deletion_pending') {
        return _PendingDeletion(onCancelled: () => setState(() {
              _destination = _resolve();
            }));
      }
      if (me.status == 'pending_consent') {
        return const _Blocked(
          message: 'A parent needs to confirm this account by email before it '
              'can be used.',
        );
      }
      if (me.status == 'suspended') {
        return const _Blocked(message: 'This account is suspended.');
      }
      if (me.needsRegistration) {
        // An account from before the age gate existed, or one that dropped out
        // of signup midway. It cannot be used until we know the age.
        return const _CompleteRegistration();
      }
      return const HomePage();
    } on OnboardingApiException catch (e) {
      return _Blocked(message: e.message);
    } on Object {
      return const SignInPage();
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Widget>(
      future: _destination,
      builder: (context, snapshot) {
        if (!snapshot.hasData) {
          return const Scaffold(body: Center(child: CircularProgressIndicator()));
        }
        return snapshot.data!;
      },
    );
  }
}

/// Wraps the age gate so a signed-in account can fill in its missing birth date
/// and land on the app without another sign-in. The gate is the root screen
/// here, so it reports completion by callback rather than popping.
class _CompleteRegistration extends StatefulWidget {
  const _CompleteRegistration();

  @override
  State<_CompleteRegistration> createState() => _CompleteRegistrationState();
}

class _CompleteRegistrationState extends State<_CompleteRegistration> {
  bool _done = false;

  @override
  Widget build(BuildContext context) {
    if (_done) return const HomePage();
    return AgeGatePage(
      completeExistingAccount: true,
      onCompleted: () => setState(() => _done = true),
    );
  }
}

/// The way back from a deletion request, before the purge runs.
///
/// This screen is the reason /v1/me answers for a blocked account: without it
/// someone who changed their mind would sign in, be refused, and have nowhere
/// to say so.
class _PendingDeletion extends StatefulWidget {
  const _PendingDeletion({required this.onCancelled});

  final VoidCallback onCancelled;

  @override
  State<_PendingDeletion> createState() => _PendingDeletionState();
}

class _PendingDeletionState extends State<_PendingDeletion> {
  final _api = OnboardingApi();
  bool _busy = false;
  String _error = '';

  Future<void> _cancel() async {
    setState(() {
      _busy = true;
      _error = '';
    });
    try {
      await _api.cancelDeletion();
      widget.onCancelled();
    } on Object catch (e) {
      setState(() {
        _error = e is OnboardingApiException ? e.message : '$e';
        _busy = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('ScriptureBuddy')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 380),
          child: Padding(
            padding: const EdgeInsets.all(32),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.delete_outline, size: 56),
                const SizedBox(height: 24),
                Text(
                  'This account is scheduled to be deleted.',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 12),
                Text(
                  'Changed your mind? You can keep it, with everything still '
                  'where you left it.',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
                const SizedBox(height: 24),
                FilledButton(
                  onPressed: _busy ? null : _cancel,
                  child: Text(_busy ? 'Restoring…' : 'Keep my account'),
                ),
                TextButton(
                  onPressed: () async {
                    await Amplify.Auth.signOut();
                    if (await resetAfterSignOut()) return;
                    if (context.mounted) {
                      Navigator.of(context).pushAndRemoveUntil(
                        MaterialPageRoute(builder: (_) => const SignInPage()),
                        (route) => false,
                      );
                    }
                  },
                  child: const Text('Sign out'),
                ),
                if (_error.isNotEmpty) ...[
                  const SizedBox(height: 16),
                  Text(
                    _error,
                    textAlign: TextAlign.center,
                    style: TextStyle(color: Theme.of(context).colorScheme.error),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _Blocked extends StatelessWidget {
  const _Blocked({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('ScriptureBuddy')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 380),
          child: Padding(
            padding: const EdgeInsets.all(32),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.lock_outline, size: 56),
                const SizedBox(height: 24),
                Text(
                  message,
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 32),
                OutlinedButton(
                  onPressed: () async {
                    await Amplify.Auth.signOut();
                    if (await resetAfterSignOut()) return;
                    if (context.mounted) {
                      Navigator.of(context).pushAndRemoveUntil(
                        MaterialPageRoute(builder: (_) => const SignInPage()),
                        (route) => false,
                      );
                    }
                  },
                  child: const Text('Sign out'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
