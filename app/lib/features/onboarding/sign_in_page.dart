import 'package:amplify_flutter/amplify_flutter.dart';
import 'package:flutter/material.dart';

import '../../core/api_client.dart';

/// M0 smoke screen: sign in against Cognito, call /v1/me, show the result.
/// Replaced by the real onboarding flow (age gate etc.) in M5.
class SignInPage extends StatefulWidget {
  const SignInPage({super.key});

  @override
  State<SignInPage> createState() => _SignInPageState();
}

class _SignInPageState extends State<SignInPage> {
  final _username = TextEditingController();
  final _password = TextEditingController();
  String _status = '';
  bool _busy = false;

  Future<void> _signIn() async {
    setState(() {
      _busy = true;
      _status = 'Signing in…';
    });
    try {
      await Amplify.Auth.signOut();
      final result = await Amplify.Auth.signIn(
        username: _username.text.trim(),
        password: _password.text,
      );
      if (!result.isSignedIn) {
        setState(() => _status = 'Additional step required: ${result.nextStep.signInStep}');
        return;
      }
      final me = await ApiClient().getJson('/v1/me');
      setState(() => _status = 'Signed in as ${me['username']} (sub ${me['sub']})');
    } on Exception catch (e) {
      setState(() => _status = 'Error: $e');
    } finally {
      setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('ScriptureBuddy')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 360),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                TextField(
                  controller: _username,
                  decoration: const InputDecoration(labelText: 'Username'),
                  autofillHints: const [AutofillHints.username],
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _password,
                  decoration: const InputDecoration(labelText: 'Password'),
                  obscureText: true,
                  autofillHints: const [AutofillHints.password],
                ),
                const SizedBox(height: 24),
                FilledButton(
                  onPressed: _busy ? null : _signIn,
                  child: const Text('Sign in'),
                ),
                const SizedBox(height: 24),
                Text(_status, textAlign: TextAlign.center),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
