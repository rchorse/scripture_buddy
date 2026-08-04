/// Friends, requests, approvals and league standings.
class Person {
  const Person({required this.userId, required this.name});

  final String userId;
  final String name;

  factory Person.fromJson(Map<String, dynamic> json) => Person(
        userId: json['user_id'] as String,
        name: json['name'] as String,
      );
}

class FriendRequestView {
  const FriendRequestView({
    required this.id,
    required this.status,
    required this.person,
  });

  final String id;
  final String status;
  final Person person;

  bool get waitingOnParent => status == 'awaiting_parent';

  factory FriendRequestView.fromJson(Map<String, dynamic> json) =>
      FriendRequestView(
        id: json['id'] as String,
        status: json['status'] as String,
        person: Person.fromJson(json),
      );
}

class SocialState {
  const SocialState({
    required this.maySocialize,
    required this.reason,
    required this.displayName,
    required this.displayNameStatus,
    required this.friends,
    required this.incoming,
    required this.outgoing,
  });

  final bool maySocialize;
  final String reason;
  final String displayName;
  final String displayNameStatus;
  final List<Person> friends;
  final List<FriendRequestView> incoming;
  final List<FriendRequestView> outgoing;

  /// A name still being screened isn't shown to anyone yet.
  bool get nameAwaitingReview => displayNameStatus == 'pending';

  factory SocialState.fromJson(Map<String, dynamic> json) => SocialState(
        maySocialize: json['may_socialize'] as bool? ?? false,
        reason: json['reason'] as String? ?? '',
        displayName: json['display_name'] as String? ?? '',
        displayNameStatus: json['display_name_status'] as String? ?? 'ok',
        friends: ((json['friends'] as List?) ?? [])
            .map((f) => Person.fromJson(f as Map<String, dynamic>))
            .toList(),
        incoming: ((json['incoming_requests'] as List?) ?? [])
            .map((r) => FriendRequestView.fromJson(r as Map<String, dynamic>))
            .toList(),
        outgoing: ((json['outgoing_requests'] as List?) ?? [])
            .map((r) => FriendRequestView.fromJson(r as Map<String, dynamic>))
            .toList(),
      );
}

class PendingApproval {
  const PendingApproval({
    required this.approvalId,
    required this.child,
    required this.wouldBefriend,
  });

  final String approvalId;
  final Person child;
  final Person wouldBefriend;

  factory PendingApproval.fromJson(Map<String, dynamic> json) => PendingApproval(
        approvalId: json['approval_id'] as String,
        child: Person.fromJson(json['child'] as Map<String, dynamic>),
        wouldBefriend:
            Person.fromJson(json['would_befriend'] as Map<String, dynamic>),
      );
}

class StandingRow {
  const StandingRow({
    required this.rank,
    required this.name,
    required this.xp,
    required this.isYou,
    this.zone = '',
  });

  final int rank;
  final String name;
  final int xp;
  final bool isYou;
  final String zone; // promote | stay | demote (leagues only)

  factory StandingRow.fromJson(Map<String, dynamic> json) => StandingRow(
        rank: json['rank'] as int? ?? 0,
        name: json['name'] as String? ?? '',
        xp: json['xp'] as int? ?? 0,
        isYou: json['is_you'] as bool? ?? false,
        zone: json['zone'] as String? ?? '',
      );
}

class Standings {
  const Standings({
    required this.available,
    required this.reason,
    required this.rows,
    this.tier = '',
    this.note = '',
  });

  final bool available;
  final String reason;
  final List<StandingRow> rows;
  final String tier;
  final String note;

  factory Standings.fromJson(Map<String, dynamic> json) => Standings(
        available: json['available'] as bool? ?? false,
        reason: json['reason'] as String? ?? '',
        tier: json['tier'] as String? ?? '',
        note: json['note'] as String? ?? '',
        rows: ((json['rows'] as List?) ?? [])
            .map((r) => StandingRow.fromJson(r as Map<String, dynamic>))
            .toList(),
      );
}
