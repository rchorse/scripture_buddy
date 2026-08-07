import 'package:flutter/material.dart';

import '../onboarding/onboarding_api.dart';
import '../onboarding/password_field.dart';
import 'family_api.dart';

/// A parent creates a child's account and sets its password.
///
/// Both steps happen here because a child account is unusable without a
/// password: it has no email, so there is no reset path a child could take on
/// their own.
class AddChildPage extends StatefulWidget {
  const AddChildPage({super.key});

  @override
  State<AddChildPage> createState() => _AddChildPageState();
}

class _AddChildPageState extends State<AddChildPage> {
  final _api = FamilyApi();
  final _username = TextEditingController();
  final _displayName = TextEditingController();
  final _password = TextEditingController();
  int? _month;
  int? _day;
  int? _year;
  bool _allowAi = true;
  bool _allowSocial = false;
  bool _busy = false;
  String _error = '';

  static const _months = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
  ];

  @override
  void dispose() {
    _username.dispose();
    _displayName.dispose();
    _password.dispose();
    super.dispose();
  }

  DateTime? get _birthDate {
    if (_month == null || _day == null || _year == null) return null;
    final date = DateTime(_year!, _month!, _day!);
    return date.month == _month && date.day == _day ? date : null;
  }

  Future<void> _create() async {
    final birthDate = _birthDate;
    final username = _username.text.trim().toLowerCase();
    if (username.length < 3 || !RegExp(r'^[a-z0-9-]+$').hasMatch(username)) {
      setState(() => _error = 'Username: 3+ characters, letters, numbers, hyphens.');
      return;
    }
    if (birthDate == null) {
      setState(() => _error = 'Choose a valid birth date.');
      return;
    }
    if (_password.text.length < 8) {
      setState(() => _error = 'Password must be at least 8 characters.');
      return;
    }
    setState(() {
      _busy = true;
      _error = '';
    });
    try {
      final created = await _api.addChild(
        username: username,
        birthDate: birthDate,
        displayName: _displayName.text.trim(),
        allowAiProcessing: _allowAi,
        allowSocial: _allowSocial,
        timezone: await OnboardingApi.deviceTimezone(),
      );
      await _api.setChildPassword(created['user_id'] as String, _password.text);
      if (!mounted) return;
      Navigator.of(context).pop(created);
    } on FamilyApiException catch (e) {
      setState(() => _error = e.message);
    } on Object catch (e) {
      setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final thisYear = DateTime.now().year;
    return Scaffold(
      appBar: AppBar(title: const Text('Add a child')),
      body: Center(
        child: SingleChildScrollView(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 400),
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  TextField(
                    controller: _username,
                    decoration: const InputDecoration(
                      labelText: 'Username',
                      helperText: 'How they sign in. Please avoid their real name.',
                    ),
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: _displayName,
                    maxLength: 24,
                    decoration: const InputDecoration(
                      labelText: 'Display name (optional)',
                      helperText: 'What friends see. Checked before it appears.',
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text('Date of birth',
                      style: Theme.of(context).textTheme.labelLarge),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Expanded(
                        flex: 3,
                        child: DropdownButtonFormField<int>(
                          initialValue: _month,
                          decoration: const InputDecoration(labelText: 'Month'),
                          items: [
                            for (var m = 1; m <= 12; m++)
                              DropdownMenuItem(value: m, child: Text(_months[m - 1])),
                          ],
                          onChanged: (v) => setState(() => _month = v),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        flex: 2,
                        child: DropdownButtonFormField<int>(
                          initialValue: _day,
                          decoration: const InputDecoration(labelText: 'Day'),
                          items: [
                            for (var d = 1; d <= 31; d++)
                              DropdownMenuItem(value: d, child: Text('$d')),
                          ],
                          onChanged: (v) => setState(() => _day = v),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        flex: 3,
                        child: DropdownButtonFormField<int>(
                          initialValue: _year,
                          decoration: const InputDecoration(labelText: 'Year'),
                          items: [
                            for (var y = thisYear; y >= thisYear - 25; y--)
                              DropdownMenuItem(value: y, child: Text('$y')),
                          ],
                          onChanged: (v) => setState(() => _year = v),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  PasswordField(
                    controller: _password,
                    label: 'Password for them',
                    autofillHint: AutofillHints.newPassword,
                    helperText: 'At least 8 characters. You can change it later.',
                  ),
                  const SizedBox(height: 16),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    value: _allowAi,
                    onChanged: (v) => setState(() => _allowAi = v),
                    title: const Text('Personalised practice'),
                    subtitle: const Text(
                      'Lets us adapt which verses they review next.',
                    ),
                  ),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    value: _allowSocial,
                    onChanged: (v) => setState(() => _allowSocial = v),
                    title: const Text('Friends and leaderboards'),
                    subtitle: const Text(
                      'There is no chat in ScriptureBuddy. This only lets them '
                      'add friends and appear on leaderboards.',
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'For a child under 13 we will email you to confirm before the '
                    'account can be used. You can change or withdraw any of these '
                    'permissions at any time.',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                  const SizedBox(height: 24),
                  FilledButton(
                    onPressed: _busy ? null : _create,
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
    );
  }
}
