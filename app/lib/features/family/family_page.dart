import 'package:flutter/material.dart';

import '../onboarding/password_field.dart';
import 'add_child_page.dart';
import 'family_api.dart';

/// The parent's view of their household.
///
/// Everything COPPA gives a parent — see what was collected, withdraw a
/// permission, delete the account — has to be reachable from here, not just
/// from an email link.
class FamilyPage extends StatefulWidget {
  const FamilyPage({super.key});

  @override
  State<FamilyPage> createState() => _FamilyPageState();
}

class _FamilyPageState extends State<FamilyPage> {
  final _api = FamilyApi();
  late Future<FamilyState> _state;

  @override
  void initState() {
    super.initState();
    _state = _api.me();
  }

  void _reload() => setState(() => _state = _api.me());

  Future<void> _guard(Future<void> Function() action, [String? success]) async {
    try {
      await action();
      if (mounted && success != null) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(success)));
      }
      _reload();
    } on FamilyApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.message)));
      }
    }
  }

  Future<void> _addChild() async {
    final created = await Navigator.of(context).push<Map<String, dynamic>>(
      MaterialPageRoute(builder: (_) => const AddChildPage()),
    );
    if (created == null || !mounted) return;
    _reload();
    final needsConsent = created['requires_consent'] as bool? ?? false;
    final hasEmail = created['parent_email_on_file'] as bool? ?? false;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          !needsConsent
              ? '${created['username']} is ready to sign in.'
              : hasEmail
                  ? 'Check your email to confirm ${created['username']}\'s account.'
                  : 'Account created, but we have no email on file to confirm it.',
        ),
      ),
    );
  }

  Future<void> _changePassword(FamilyMember child) async {
    final controller = TextEditingController();
    final password = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text('Password for ${child.username}'),
        content: PasswordField(
          controller: controller,
          label: 'New password',
          helperText: 'At least 8 characters.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, controller.text),
            child: const Text('Save'),
          ),
        ],
      ),
    );
    if (password == null || password.length < 8) return;
    await _guard(
      () => _api.setChildPassword(child.userId, password),
      'Password updated.',
    );
  }

  Future<void> _delete(FamilyMember child) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text('Delete ${child.username}?'),
        content: const Text(
          'Everything they have done is erased after 30 days. You can undo this '
          'from here until then.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Keep account'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    await _guard(() => _api.deleteChild(child.userId), 'Scheduled for deletion.');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Family')),
      body: FutureBuilder<FamilyState>(
        future: _state,
        builder: (context, snapshot) {
          if (snapshot.hasError) {
            return _Message(text: '${snapshot.error}');
          }
          if (!snapshot.hasData) {
            return const Center(child: CircularProgressIndicator());
          }
          final state = snapshot.data!;
          if (state.children.isEmpty) {
            return const _Message(
              text: 'No child accounts yet.\n\n'
                  'Add one to set up ScriptureBuddy for a child in your care.',
            );
          }
          return RefreshIndicator(
            onRefresh: () async => _reload(),
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                for (final child in state.children)
                  Card(
                    child: Column(
                      children: [
                        ListTile(
                          leading: CircleAvatar(
                            child: Text(child.username.isEmpty
                                ? '?'
                                : child.username[0].toUpperCase()),
                          ),
                          title: Text(child.displayName.isEmpty
                              ? child.username
                              : '${child.displayName} (${child.username})'),
                          subtitle: Text(_statusLine(child)),
                          trailing: PopupMenuButton<String>(
                            onSelected: (choice) {
                              if (choice == 'password') _changePassword(child);
                              if (choice == 'delete') _delete(child);
                              if (choice == 'undelete') {
                                _guard(() => _api.cancelDeletion(child.userId),
                                    'Deletion cancelled.');
                              }
                            },
                            itemBuilder: (_) => [
                              const PopupMenuItem(
                                value: 'password',
                                child: Text('Change password'),
                              ),
                              if (child.status == 'deletion_pending')
                                const PopupMenuItem(
                                  value: 'undelete',
                                  child: Text('Cancel deletion'),
                                )
                              else
                                const PopupMenuItem(
                                  value: 'delete',
                                  child: Text('Delete account'),
                                ),
                            ],
                          ),
                        ),
                        if (child.isUnder13)
                          Padding(
                            padding:
                                const EdgeInsets.fromLTRB(16, 0, 16, 12),
                            child: Align(
                              alignment: Alignment.centerLeft,
                              child: Wrap(
                                spacing: 6,
                                children: [
                                  for (final scope in const [
                                    'account',
                                    'ai_processing',
                                    'social',
                                  ])
                                    Chip(
                                      label: Text(_scopeLabel(scope)),
                                      avatar: Icon(
                                        child.consents.contains(scope)
                                            ? Icons.check_circle
                                            : Icons.remove_circle_outline,
                                        size: 18,
                                      ),
                                    ),
                                ],
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
              ],
            ),
          );
        },
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _addChild,
        icon: const Icon(Icons.person_add),
        label: const Text('Add a child'),
      ),
    );
  }

  static String _scopeLabel(String scope) => switch (scope) {
        'account' => 'Account',
        'ai_processing' => 'Personalised practice',
        'social' => 'Friends',
        _ => scope,
      };

  static String _statusLine(FamilyMember child) {
    if (child.status == 'deletion_pending') return 'Scheduled for deletion';
    if (child.awaitingConsent) return 'Waiting for your email confirmation';
    if (!child.claimed) return 'Ready — has not signed in yet';
    return 'Active';
  }
}

class _Message extends StatelessWidget {
  const _Message({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Text(
            text,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyLarge,
          ),
        ),
      );
}
