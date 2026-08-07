import 'package:amplify_flutter/amplify_flutter.dart';
import 'package:flutter/material.dart';

import '../reader/home_page.dart';
import 'onboarding_api.dart';

/// Email confirmation, then the one-time registration call.
///
/// The birth date is carried from the age gate and only reaches the server
/// here, once there is an account to attach it to. Registration is what turns
/// an age-unknown row into a real profile, so it runs before the app opens —
/// an account that skipped it cannot act as a parent.
class ConfirmSignUpPage extends StatefulWidget {
  const ConfirmSignUpPage({
    super.key,
    required this.username,
    required this.password,
    required this.birthDate,
    required this.email,
    this.alreadyConfirmed = false,
  });

  final String username;
  final String password;
  final DateTime birthDate;
  final String email;

  /// True when the pool is configured to auto-confirm, so no code was sent.
  final bool alreadyConfirmed;

  @override
  State<ConfirmSignUpPage> createState() => _ConfirmSignUpPageState();
}

class _ConfirmSignUpPageState extends State<ConfirmSignUpPage> {
  final _api = OnboardingApi();
  final _code = TextEditingController();
  String _error = '';
  String _notice = '';
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    if (widget.alreadyConfirmed) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _finish());
    }
  }

  @override
  void dispose() {
    _code.dispose();
    super.dispose();
  }

  Future<void> _confirm() async {
    if (_code.text.trim().isEmpty) {
      setState(() => _error = 'Enter the code from your email.');
      return;
    }
    setState(() {
      _busy = true;
      _error = '';
    });
    try {
      await Amplify.Auth.confirmSignUp(
        username: widget.username,
        confirmationCode: _code.text.trim(),
      );
      await _finish();
    } on AuthException catch (e) {
      setState(() => _error = e.message);
    } on Object catch (e) {
      setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  /// Sign in, record the birth date, then open the app.
  Future<void> _finish() async {
    setState(() {
      _busy = true;
      _error = '';
    });
    try {
      final signIn = await Amplify.Auth.signIn(
        username: widget.username,
        password: widget.password,
      );
      if (!signIn.isSignedIn) {
        setState(() => _error = 'Confirmed. Please sign in to continue.');
        return;
      }
      await _api.register(widget.birthDate);
      if (!mounted) return;
      Navigator.of(context).pushAndRemoveUntil(
        MaterialPageRoute(builder: (_) => const HomePage()),
        (route) => false,
      );
    } on AuthException catch (e) {
      setState(() => _error = e.message);
    } on OnboardingApiException catch (e) {
      setState(() => _error = e.message);
    } on Object catch (e) {
      setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _resend() async {
    setState(() {
      _notice = '';
      _error = '';
    });
    try {
      await Amplify.Auth.resendSignUpCode(username: widget.username);
      setState(() => _notice = 'We sent a new code to ${widget.email}.');
    } on AuthException catch (e) {
      setState(() => _error = e.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Confirm your email')),
      body: Center(
        child: SingleChildScrollView(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 360),
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    'We sent a code to ${widget.email}.',
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                  const SizedBox(height: 24),
                  TextField(
                    controller: _code,
                    keyboardType: TextInputType.number,
                    autofillHints: const [AutofillHints.oneTimeCode],
                    decoration: const InputDecoration(labelText: 'Confirmation code'),
                    onSubmitted: (_) => _confirm(),
                  ),
                  const SizedBox(height: 24),
                  FilledButton(
                    onPressed: _busy ? null : _confirm,
                    child: Text(_busy ? 'Confirming…' : 'Confirm'),
                  ),
                  TextButton(
                    onPressed: _busy ? null : _resend,
                    child: const Text('Send a new code'),
                  ),
                  if (_notice.isNotEmpty)
                    Text(_notice, textAlign: TextAlign.center),
                  if (_error.isNotEmpty) ...[
                    const SizedBox(height: 8),
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
    );
  }
}
