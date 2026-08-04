import 'package:flutter/material.dart';

import 'social_api.dart';
import 'social_models.dart';

/// Where a parent approves each specific friendship for their child.
///
/// Deliberately per-person rather than a blanket setting: consenting to
/// "friends" in general is not the same as agreeing to this particular one.
class ApprovalsPage extends StatefulWidget {
  const ApprovalsPage({super.key});

  @override
  State<ApprovalsPage> createState() => _ApprovalsPageState();
}

class _ApprovalsPageState extends State<ApprovalsPage> {
  final _api = SocialApi();
  late Future<List<PendingApproval>> _approvals;

  @override
  void initState() {
    super.initState();
    _approvals = _api.pendingApprovals();
  }

  Future<void> _decide(PendingApproval approval, bool approve) async {
    try {
      await _api.decideApproval(approval.approvalId, approve);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              approve
                  ? '${approval.child.name} can now be friends with '
                      '${approval.wouldBefriend.name}.'
                  : 'Declined.',
            ),
          ),
        );
      }
      setState(() => _approvals = _api.pendingApprovals());
    } on SocialApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.message)));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Friend approvals')),
      body: FutureBuilder<List<PendingApproval>>(
        future: _approvals,
        builder: (context, snapshot) {
          if (snapshot.hasError) {
            return Center(child: Text('${snapshot.error}'));
          }
          if (!snapshot.hasData) {
            return const Center(child: CircularProgressIndicator());
          }
          final approvals = snapshot.data!;
          if (approvals.isEmpty) {
            return const Center(
              child: Padding(
                padding: EdgeInsets.all(32),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.check_circle_outline,
                        size: 56, color: Colors.green),
                    SizedBox(height: 16),
                    Text('Nothing waiting for you.', textAlign: TextAlign.center),
                  ],
                ),
              ),
            );
          }
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Text(
                  'Your child can only see this person\'s progress and compete '
                  'with them. There is no messaging in ScriptureBuddy.',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
              for (final approval in approvals)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${approval.child.name} would like to be friends with '
                          '${approval.wouldBefriend.name}',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        const SizedBox(height: 12),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.end,
                          children: [
                            TextButton(
                              onPressed: () => _decide(approval, false),
                              child: const Text('Not now'),
                            ),
                            const SizedBox(width: 8),
                            FilledButton(
                              onPressed: () => _decide(approval, true),
                              child: const Text('Approve'),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}
