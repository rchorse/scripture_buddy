import 'package:flutter/material.dart';

import 'onboarding_api.dart';
import 'parent_required_page.dart';
import 'sign_up_page.dart';

/// Neutral age gate.
///
/// It asks for a birth date and never for "are you over 13?" — a yes/no
/// question telegraphs which answer unlocks the app, which is exactly what the
/// FTC's neutral-gate guidance exists to prevent. The date is sent to a
/// deliberately anonymous endpoint: nothing is stored, so a child who is turned
/// away leaves no record behind.
class AgeGatePage extends StatefulWidget {
  const AgeGatePage({
    super.key,
    this.completeExistingAccount = false,
    this.onCompleted,
  });

  /// True when an already-signed-in account is missing its birth date, so the
  /// answer is saved to that account instead of starting a new signup.
  final bool completeExistingAccount;

  /// Called instead of popping once registration succeeds. Used when the gate
  /// is the root screen and so has nothing to pop back to.
  final VoidCallback? onCompleted;

  @override
  State<AgeGatePage> createState() => _AgeGatePageState();
}

class _AgeGatePageState extends State<AgeGatePage> {
  final _api = OnboardingApi();
  int? _month;
  int? _day;
  int? _year;
  String _error = '';
  bool _busy = false;

  static const _months = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
  ];

  bool get _complete => _month != null && _day != null && _year != null;

  /// Guards against 31 February before the server has to.
  DateTime? get _birthDate {
    if (!_complete) return null;
    final date = DateTime(_year!, _month!, _day!);
    return date.month == _month && date.day == _day ? date : null;
  }

  Future<void> _continue() async {
    final birthDate = _birthDate;
    if (birthDate == null) {
      setState(() => _error = 'That date does not exist — please check it.');
      return;
    }
    setState(() {
      _busy = true;
      _error = '';
    });
    try {
      final result = await _api.ageGate(birthDate);
      if (!mounted) return;
      if (result.requiresParent) {
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(
            builder: (_) => ParentRequiredPage(message: result.message),
          ),
        );
        return;
      }
      if (widget.completeExistingAccount) {
        await _api.register(birthDate);
        if (!mounted) return;
        final done = widget.onCompleted;
        if (done != null) {
          done();
        } else {
          Navigator.of(context).pop(true);
        }
        return;
      }
      Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => SignUpPage(birthDate: birthDate)),
      );
    } on Object catch (e) {
      setState(() => _error = e is OnboardingApiException ? e.message : '$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final thisYear = DateTime.now().year;
    return Scaffold(
      appBar: AppBar(title: const Text('Your birthday')),
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
                    'When were you born?',
                    style: Theme.of(context).textTheme.headlineSmall,
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'We ask so the app is set up correctly for your age.',
                    style: Theme.of(context).textTheme.bodySmall,
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 24),
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
                            for (var y = thisYear; y >= thisYear - 100; y--)
                              DropdownMenuItem(value: y, child: Text('$y')),
                          ],
                          onChanged: (v) => setState(() => _year = v),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 24),
                  FilledButton(
                    onPressed: _busy || !_complete ? null : _continue,
                    child: Text(_busy ? 'Checking…' : 'Continue'),
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
