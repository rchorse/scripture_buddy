import 'package:amplify_flutter/amplify_flutter.dart';
import 'package:flutter/material.dart';

import 'password_field.dart';

/// Password reset by emailed code.
///
/// Only works for accounts that have an email — which means adults and teens.
/// Child accounts deliberately have no email on file, so a parent resets those
/// from the Family screen instead; the copy below says so rather than leaving a
/// child staring at a code that will never arrive.
class ForgotPasswordPage extends StatefulWidget {
  const ForgotPasswordPage({super.key, this.initialUsername = ''});

  final String initialUsername;

  @override
  State<ForgotPasswordPage> createState() => _ForgotPasswordPageState();
}

class _ForgotPasswordPageState extends State<ForgotPasswordPage> {
  late final _username = TextEditingController(text: widget.initialUsername);
  final _code = TextEditingController();
  final _newPassword = TextEditingController();
  bool _codeSent = false;
  bool _busy = false;
  String _error = '';
  String _notice = '';

  @override
  void dispose() {
    _username.dispose();
    _code.dispose();
    _newPassword.dispose();
    super.dispose();
  }

  Future<void> _sendCode() async {
    if (_username.text.trim().isEmpty) {
      setState(() => _error = 'Enter your username or email.');
      return;
    }
    setState(() {
      _busy = true;
      _error = '';
      _notice = '';
    });
    try {
      final result =
          await Amplify.Auth.resetPassword(username: _username.text.trim());
      setState(() {
        _codeSent = !result.isPasswordReset;
        _notice = 'If that account has an email on file, a code is on its way.';
      });
    } on AuthException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _confirm() async {
    if (_code.text.trim().isEmpty || _newPassword.text.length < 8) {
      setState(() => _error = 'Enter the code and a new password of 8+ characters.');
      return;
    }
    setState(() {
      _busy = true;
      _error = '';
    });
    try {
      await Amplify.Auth.confirmResetPassword(
        username: _username.text.trim(),
        newPassword: _newPassword.text,
        confirmationCode: _code.text.trim(),
      );
      if (!mounted) return;
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Password changed — sign in with it now.')),
      );
    } on AuthException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Reset your password')),
      body: Center(
        child: SingleChildScrollView(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 360),
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  TextField(
                    controller: _username,
                    enabled: !_codeSent,
                    autofillHints: const [AutofillHints.username],
                    decoration: const InputDecoration(
                      labelText: 'Username or email',
                    ),
                    onSubmitted: (_) => _sendCode(),
                  ),
                  const SizedBox(height: 16),
                  if (!_codeSent)
                    FilledButton(
                      onPressed: _busy ? null : _sendCode,
                      child: Text(_busy ? 'Sending…' : 'Send code'),
                    ),
                  if (_codeSent) ...[
                    TextField(
                      controller: _code,
                      keyboardType: TextInputType.number,
                      autofillHints: const [AutofillHints.oneTimeCode],
                      decoration: const InputDecoration(labelText: 'Code from email'),
                    ),
                    const SizedBox(height: 16),
                    PasswordField(
                      controller: _newPassword,
                      label: 'New password',
                      autofillHint: AutofillHints.newPassword,
                      helperText: 'At least 8 characters.',
                      onSubmitted: _confirm,
                    ),
                    const SizedBox(height: 24),
                    FilledButton(
                      onPressed: _busy ? null : _confirm,
                      child: Text(_busy ? 'Saving…' : 'Set new password'),
                    ),
                  ],
                  if (_notice.isNotEmpty) ...[
                    const SizedBox(height: 16),
                    Text(_notice, textAlign: TextAlign.center),
                  ],
                  if (_error.isNotEmpty) ...[
                    const SizedBox(height: 16),
                    Text(
                      _error,
                      textAlign: TextAlign.center,
                      style: TextStyle(color: Theme.of(context).colorScheme.error),
                    ),
                  ],
                  const SizedBox(height: 32),
                  Text(
                    'Under 13? Your account does not use email — ask the parent '
                    'who set it up to choose a new password for you.',
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
