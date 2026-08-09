import 'package:flutter/material.dart';

import '../../core/hive_theme.dart';

/// Clips a widget to a flat-top hexagon — a honeycomb cell.
///
/// Drawn rather than shipped as an image so it stays sharp at any size and
/// recolours with the node's state instead of needing an asset per variant.
class HexagonClipper extends CustomClipper<Path> {
  const HexagonClipper();

  @override
  Path getClip(Size size) {
    final w = size.width;
    final h = size.height;
    return Path()
      ..moveTo(w * 0.5, 0)
      ..lineTo(w, h * 0.25)
      ..lineTo(w, h * 0.75)
      ..lineTo(w * 0.5, h)
      ..lineTo(0, h * 0.75)
      ..lineTo(0, h * 0.25)
      ..close();
  }

  @override
  bool shouldReclip(covariant CustomClipper<Path> oldClipper) => false;
}

enum NodeState { locked, inProgress, completed }

/// One cell on the Honeycomb Path.
class HoneycombNode extends StatelessWidget {
  const HoneycombNode({
    super.key,
    required this.state,
    required this.label,
    this.onTap,
    this.width = 80,
    this.height = 92,
  });

  final NodeState state;
  final String label;
  final VoidCallback? onTap;
  final double width;
  final double height;

  Color _fill(BuildContext context) => switch (state) {
        NodeState.locked => Theme.of(context).colorScheme.outline,
        NodeState.inProgress => HiveTheme.royalAmber,
        NodeState.completed => HiveTheme.honeyGolden,
      };

  @override
  Widget build(BuildContext context) {
    final locked = state == NodeState.locked;
    return Semantics(
      button: !locked,
      label: switch (state) {
        NodeState.locked => '$label, locked',
        NodeState.inProgress => '$label, in progress',
        NodeState.completed => '$label, completed',
      },
      child: GestureDetector(
        onTap: locked ? null : onTap,
        child: ClipPath(
          clipper: const HexagonClipper(),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 250),
            width: width,
            height: height,
            color: _fill(context),
            child: Center(
              child: locked
                  ? const Icon(Icons.lock_outline, color: Colors.white70)
                  : Text(
                      label,
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        color: HiveTheme.deepMidnight,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
            ),
          ),
        ),
      ),
    );
  }
}
