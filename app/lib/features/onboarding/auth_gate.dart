import 'package:amplify_flutter/amplify_flutter.dart';
import 'package:flutter/material.dart';

import '../reader/home_page.dart';
import 'age_gate_page.dart';
import 'onboarding_api.dart';
import 'sign_in_page.dart';

/// Decides the first screen: sign in, finish registering, or the app.
///
/// Restoring an existing session here is what lets the sign-in screen drop its
/// old `signOut()`-before-`signIn()` call. That call existed to clear a stale
/// session, but it is a network round trip that can hang on web and strand the
/// UI on "Signing in…" forever.
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
      if (me.needsRegistration) {
        // An account from before the age gate existed, or one that dropped out
        // of signup midway. It cannot be used until we know the age.
        return const _CompleteRegistration();
      }
      return const HomePage();
    } on OnboardingApiException catch (e) {
      // The server refuses accounts awaiting consent or pending deletion, and
      // its message is written for the reader.
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
