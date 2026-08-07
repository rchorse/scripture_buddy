import 'package:amplify_flutter/amplify_flutter.dart';
import 'package:flutter/material.dart';

import '../reader/home_page.dart';
import 'age_gate_page.dart';
import 'forgot_password_page.dart';
import 'onboarding_api.dart';
import 'password_field.dart';

/// Sign in, with the routes out to account creation and password reset.
class SignInPage extends StatefulWidget {
  const SignInPage({super.key});

  @override
  State<SignInPage> createState() => _SignInPageState();
}

class _SignInPageState extends State<SignInPage> {
  final _api = OnboardingApi();
  final _username = TextEditingController();
  final _password = TextEditingController();
  String _status = '';
  bool _busy = false;

  @override
  void dispose() {
    _username.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _signIn() async {
    if (_username.text.trim().isEmpty || _password.text.isEmpty) {
      setState(() => _status = 'Enter your username and password.');
      return;
    }
    setState(() {
      _busy = true;
      _status = 'Signing in…';
    });
    try {
      final result = await Amplify.Auth.signIn(
        username: _username.text.trim().toLowerCase(),
        password: _password.text,
      );
      if (!result.isSignedIn) {
        setState(() => _status =
            'Additional step required: ${result.nextStep.signInStep.name}');
        return;
      }
      await _afterSignIn();
    } on AuthException catch (e) {
      // A session left over from a previous visit blocks a fresh sign-in. Clear
      // it and let the reader try again rather than signing out pre-emptively
      // on every attempt, which is a round trip that can hang on web.
      if (e is SignedOutException || e.message.contains('already a user signed in')) {
        await Amplify.Auth.signOut();
        setState(() => _status = 'Please try that once more.');
        return;
      }
      setState(() => _status = e.message);
    } on Object catch (e) {
      setState(() => _status = '$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  /// Registration is what records the age, so an account missing it goes
  /// through the gate before the app opens.
  Future<void> _afterSignIn() async {
    final me = await _api.me();
    if (!mounted) return;
    if (me.needsRegistration) {
      final done = await Navigator.of(context).push<bool>(
        MaterialPageRoute(
          builder: (_) => const AgeGatePage(completeExistingAccount: true),
        ),
      );
      if (done != true) return;
    }
    if (!mounted) return;
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => const HomePage()),
      (route) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('ScriptureBuddy')),
      body: Center(
        child: SingleChildScrollView(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 360),
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: AutofillGroup(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    TextField(
                      controller: _username,
                      autofillHints: const [AutofillHints.username],
                      decoration: const InputDecoration(labelText: 'Username'),
                    ),
                    const SizedBox(height: 12),
                    PasswordField(
                      controller: _password,
                      onSubmitted: _signIn,
                    ),
                    const SizedBox(height: 24),
                    FilledButton(
                      onPressed: _busy ? null : _signIn,
                      child: const Text('Sign in'),
                    ),
                    const SizedBox(height: 8),
                    TextButton(
                      onPressed: _busy
                          ? null
                          : () => Navigator.of(context).push(
                                MaterialPageRoute(
                                  builder: (_) => ForgotPasswordPage(
                                    initialUsername: _username.text.trim(),
                                  ),
                                ),
                              ),
                      child: const Text('Forgot your password?'),
                    ),
                    const Divider(height: 32),
                    OutlinedButton(
                      onPressed: _busy
                          ? null
                          : () => Navigator.of(context).push(
                                MaterialPageRoute(
                                  builder: (_) => const AgeGatePage(),
                                ),
                              ),
                      child: const Text('Create an account'),
                    ),
                    if (_status.isNotEmpty) ...[
                      const SizedBox(height: 24),
                      Text(_status, textAlign: TextAlign.center),
                    ],
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
