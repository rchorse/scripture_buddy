import 'package:flutter/material.dart';

import 'social_api.dart';
import 'social_models.dart';

/// Friends, requests, and the display name others see.
class FriendsPage extends StatefulWidget {
  const FriendsPage({super.key});

  @override
  State<FriendsPage> createState() => _FriendsPageState();
}

class _FriendsPageState extends State<FriendsPage> {
  final _api = SocialApi();
  late Future<SocialState> _state;

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
    } on SocialApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.message)));
      }
    }
  }

  /// Accepting may not complete the friendship — if either side is a minor it
  /// moves to awaiting_parent, and the server tells us to say so.
  Future<void> _acceptRequest(String requestId) async {
    String note = '';
    await _guard(() async {
      note = await _api.accept(requestId);
    });
    if (!mounted || note.isEmpty) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(note)));
  }

  Future<void> _addFriend() async {
    final controller = TextEditingController();
    final username = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Add a friend'),
        content: TextField(
          controller: controller,
          autofocus: true,
          decoration: const InputDecoration(
            labelText: 'Their username',
            helperText: 'They (and a parent, if they are under 18) must agree.',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, controller.text.trim()),
            child: const Text('Send request'),
          ),
        ],
      ),
    );
    if (username == null || username.isEmpty) return;
    await _guard(() => _api.sendRequest(username), 'Request sent.');
  }

  Future<void> _editDisplayName(String current) async {
    final controller = TextEditingController(text: current);
    final name = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Display name'),
        content: TextField(
          controller: controller,
          autofocus: true,
          maxLength: 24,
          decoration: const InputDecoration(
            labelText: 'What friends see',
            helperText: 'Please don\'t use your real full name.',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, controller.text.trim()),
            child: const Text('Save'),
          ),
        ],
      ),
    );
    if (name == null || name.isEmpty) return;
    await _guard(() async {
      final result = await _api.setDisplayName(name);
      if (mounted && result['status'] == 'pending') {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text("We're checking that name — it'll appear shortly."),
          ),
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Friends')),
      body: FutureBuilder<SocialState>(
        future: _state,
        builder: (context, snapshot) {
          if (snapshot.hasError) {
            return Center(child: Text('${snapshot.error}'));
          }
          if (!snapshot.hasData) {
            return const Center(child: CircularProgressIndicator());
          }
          final state = snapshot.data!;
          if (!state.maySocialize) {
            return _Unavailable(reason: state.reason);
          }
          return RefreshIndicator(
            onRefresh: () async => _reload(),
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Card(
                  child: ListTile(
                    leading: const Icon(Icons.badge_outlined),
                    title: Text(state.displayName),
                    subtitle: Text(
                      state.nameAwaitingReview
                          ? 'Being checked — friends still see your username'
                          : 'What friends see',
                    ),
                    trailing: const Icon(Icons.edit),
                    onTap: () => _editDisplayName(state.displayName),
                  ),
                ),
                if (state.incoming.isNotEmpty) ...[
                  const _Heading('Requests for you'),
                  for (final request in state.incoming)
                    Card(
                      child: ListTile(
                        title: Text(request.person.name),
                        subtitle: request.waitingOnParent
                            ? const Text('Waiting for a parent to approve')
                            : null,
                        trailing: request.waitingOnParent
                            ? null
                            : Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  IconButton(
                                    tooltip: 'Accept',
                                    icon: const Icon(Icons.check,
                                        color: Color(0xFF2E7D32)),
                                    onPressed: () => _acceptRequest(request.id),
                                  ),
                                  IconButton(
                                    tooltip: 'Decline',
                                    icon: const Icon(Icons.close),
                                    onPressed: () =>
                                        _guard(() => _api.decline(request.id)),
                                  ),
                                ],
                              ),
                      ),
                    ),
                ],
                if (state.outgoing.isNotEmpty) ...[
                  const _Heading('Sent'),
                  for (final request in state.outgoing)
                    Card(
                      child: ListTile(
                        title: Text(request.person.name),
                        subtitle: Text(
                          request.waitingOnParent
                              ? 'Waiting for a parent to approve'
                              : 'Waiting for them to accept',
                        ),
                        trailing: TextButton(
                          onPressed: () => _guard(() => _api.decline(request.id)),
                          child: const Text('Cancel'),
                        ),
                      ),
                    ),
                ],
                const _Heading('Friends'),
                if (state.friends.isEmpty)
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 24),
                    child: Center(
                      child: Text('No friends yet — add someone by username.'),
                    ),
                  ),
                for (final friend in state.friends)
                  Card(
                    child: ListTile(
                      leading: CircleAvatar(
                        child: Text(
                          friend.name.isEmpty ? '?' : friend.name[0].toUpperCase(),
                        ),
                      ),
                      title: Text(friend.name),
                      trailing: PopupMenuButton<String>(
                        onSelected: (choice) {
                          if (choice == 'remove') {
                            _guard(() => _api.unfriend(friend.userId), 'Removed.');
                          } else if (choice == 'block') {
                            _guard(() => _api.block(friend.userId), 'Blocked.');
                          }
                        },
                        itemBuilder: (_) => const [
                          PopupMenuItem(value: 'remove', child: Text('Remove friend')),
                          PopupMenuItem(value: 'block', child: Text('Block')),
                        ],
                      ),
                    ),
                  ),
              ],
            ),
          );
        },
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _addFriend,
        icon: const Icon(Icons.person_add),
        label: const Text('Add friend'),
      ),
    );
  }
}

class _Heading extends StatelessWidget {
  const _Heading(this.text);
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(4, 20, 4, 8),
        child: Text(text, style: Theme.of(context).textTheme.titleSmall),
      );
}

class _Unavailable extends StatelessWidget {
  const _Unavailable({required this.reason});
  final String reason;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.lock_outline, size: 56),
              const SizedBox(height: 16),
              Text(
                reason.isEmpty ? 'Friends are not available.' : reason,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyLarge,
              ),
            ],
          ),
        ),
      );
}
