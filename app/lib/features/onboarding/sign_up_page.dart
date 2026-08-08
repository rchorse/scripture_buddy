import 'package:amplify_flutter/amplify_flutter.dart';
import 'package:flutter/material.dart';

import '../../core/auth_timeout.dart';

import 'confirm_sign_up_page.dart';
import 'password_field.dart';

/// Account creation for anyone the age gate let through (13+).
///
/// Reached only from [AgeGatePage], which hands over the birth date it already
/// collected — there is no route here that skips the gate.
class SignUpPage extends StatefulWidget {
  const SignUpPage({super.key, required this.birthDate});

  final DateTime birthDate;

  @override
  State<SignUpPage> createState() => _SignUpPageState();
}

class _SignUpPageState extends State<SignUpPage> {
  final _username = TextEditingController();
  final _email = TextEditingController();
  final _password = TextEditingController();
  String _error = '';
  bool _busy = false;

  @override
  void dispose() {
    _username.dispose();
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  String? _validate() {
    final username = _username.text.trim();
    if (username.length < 3 || username.length > 30) {
      return 'Username must be 3–30 characters.';
    }
    if (!RegExp(r'^[a-zA-Z0-9-]+$').hasMatch(username)) {
      return 'Username can use letters, numbers and hyphens only.';
    }
    if (!_email.text.trim().contains('@')) {
      return 'Enter a valid email address.';
    }
    if (_password.text.length < 8) {
      return 'Password must be at least 8 characters.';
    }
    return null;
  }

  Future<void> _signUp() async {
    final problem = _validate();
    if (problem != null) {
      setState(() => _error = problem);
      return;
    }
    setState(() {
      _busy = true;
      _error = '';
    });
    try {
      final result = await guardAuth(
        Amplify.Auth.signUp(
          username: _username.text.trim().toLowerCase(),
          password: _password.text,
          options: SignUpOptions(
            userAttributes: {AuthUserAttributeKey.email: _email.text.trim()},
          ),
        ),
        what: 'Creating your account',
      );
      if (!mounted) return;
      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => ConfirmSignUpPage(
            username: _username.text.trim().toLowerCase(),
            password: _password.text,
            birthDate: widget.birthDate,
            email: _email.text.trim(),
            alreadyConfirmed: result.isSignUpComplete,
          ),
        ),
      );
    } on AuthTimeout catch (e) {
      setState(() => _error = e.message);
    } on AuthException catch (e) {
      setState(() => _error = e.message);
    } on Object catch (e) {
      setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Create your account')),
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
                      autofillHints: const [AutofillHints.newUsername],
                      decoration: const InputDecoration(
                        labelText: 'Username',
                        helperText: 'What you sign in with. Friends can see this.',
                      ),
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: _email,
                      keyboardType: TextInputType.emailAddress,
                      autofillHints: const [AutofillHints.email],
                      decoration: const InputDecoration(
                        labelText: 'Email',
                        helperText: 'Used to confirm your account and reset your '
                            'password.',
                      ),
                    ),
                    const SizedBox(height: 16),
                    PasswordField(
                      controller: _password,
                      autofillHint: AutofillHints.newPassword,
                      helperText: 'At least 8 characters.',
                      onSubmitted: _signUp,
                    ),
                    const SizedBox(height: 24),
                    FilledButton(
                      onPressed: _busy ? null : _signUp,
                      child: Text(_busy ? 'Creating…' : 'Create account'),
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
        ),
      ),
    );
  }
}
