import 'package:flutter/material.dart';

import 'lessons_api.dart';

/// Reasons mirror the server's enum; the note is free text seen only by the
/// curator, never by other learners.
const _reasons = <String, String>{
  'wrong_answer': 'The marked answer is wrong',
  'not_in_text': "It's not in the scripture text",
  'confusing': 'The question is confusing',
  'typo': 'Spelling or formatting problem',
  'other': 'Something else',
};

Future<void> showFlagSheet(
  BuildContext context,
  LessonsApi api,
  String exerciseId,
) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    builder: (sheetContext) => _FlagSheet(api: api, exerciseId: exerciseId),
  );
}

class _FlagSheet extends StatefulWidget {
  const _FlagSheet({required this.api, required this.exerciseId});

  final LessonsApi api;
  final String exerciseId;

  @override
  State<_FlagSheet> createState() => _FlagSheetState();
}

class _FlagSheetState extends State<_FlagSheet> {
  String _reason = 'wrong_answer';
  final _note = TextEditingController();
  bool _sending = false;

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    setState(() => _sending = true);
    try {
      await widget.api.flag(widget.exerciseId, _reason, _note.text.trim());
      if (mounted) {
        Navigator.of(context).pop();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Thanks — we\'ll take a look at this one.')),
        );
      }
    } catch (e) {
      if (mounted) {
        setState(() => _sending = false);
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Could not send: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
        left: 20,
        right: 20,
        top: 20,
        bottom: MediaQuery.of(context).viewInsets.bottom + 20,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Report a problem',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 12),
          RadioGroup<String>(
            groupValue: _reason,
            onChanged: (v) => setState(() => _reason = v!),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                for (final entry in _reasons.entries)
                  RadioListTile<String>(
                    contentPadding: EdgeInsets.zero,
                    dense: true,
                    value: entry.key,
                    title: Text(entry.value),
                  ),
              ],
            ),
          ),
          TextField(
            controller: _note,
            decoration: const InputDecoration(
              labelText: 'Anything else? (optional)',
              border: OutlineInputBorder(),
            ),
            maxLines: 2,
            maxLength: 300,
          ),
          const SizedBox(height: 8),
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              TextButton(
                onPressed: _sending ? null : () => Navigator.of(context).pop(),
                child: const Text('Cancel'),
              ),
              const SizedBox(width: 8),
              FilledButton(
                onPressed: _sending ? null : _send,
                child: const Text('Send report'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
