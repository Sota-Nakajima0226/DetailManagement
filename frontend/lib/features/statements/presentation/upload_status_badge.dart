import 'package:flutter/material.dart';

import '../../upload/models/upload_status.dart';

/// `GET /statements/upload-status` の対象カードを、取込済み / 未取込で示す。
class UploadStatusBadge extends StatelessWidget {
  const UploadStatusBadge({
    super.key,
    required this.status,
    this.isLoading = false,
  });

  final UploadStatus? status;
  final bool isLoading;

  @override
  Widget build(BuildContext context) {
    if (status == null) {
      if (!isLoading) return const SizedBox.shrink();
      return const LinearProgressIndicator();
    }

    final missingCodes = status!.missing.map((issuer) => issuer.code).toSet();
    final scheme = Theme.of(context).colorScheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('取込状況'),
        const SizedBox(height: 8),
        if (status!.expectedIssuers.isEmpty)
          const Text('取込対象のカードはありません')
        else
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final issuer in status!.expectedIssuers)
                _IssuerChip(
                  label: issuer.displayName,
                  missing: missingCodes.contains(issuer.code),
                  scheme: scheme,
                ),
            ],
          ),
      ],
    );
  }
}

class _IssuerChip extends StatelessWidget {
  const _IssuerChip({
    required this.label,
    required this.missing,
    required this.scheme,
  });

  final String label;
  final bool missing;
  final ColorScheme scheme;

  @override
  Widget build(BuildContext context) {
    final color = missing ? scheme.error : scheme.primary;
    return Chip(
      visualDensity: VisualDensity.compact,
      avatar: Icon(missing ? Icons.close : Icons.check, size: 18, color: color),
      label: Text(label),
      backgroundColor: missing ? scheme.errorContainer : null,
      side: BorderSide(color: color),
    );
  }
}
