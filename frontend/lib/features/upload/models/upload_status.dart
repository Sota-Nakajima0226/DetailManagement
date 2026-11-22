class UploadStatusIssuer {
  const UploadStatusIssuer({
    required this.code,
    required this.displayName,
  });

  final String code;
  final String displayName;

  factory UploadStatusIssuer.fromJson(Map<String, dynamic> json) {
    return UploadStatusIssuer(
      code: json['code'] as String,
      displayName: json['display_name'] as String,
    );
  }
}

class UploadStatusUploadedIssuer {
  const UploadStatusUploadedIssuer({
    required this.code,
    required this.displayName,
    required this.statementId,
    this.uploadedAt,
  });

  final String code;
  final String displayName;
  final int statementId;
  final DateTime? uploadedAt;

  factory UploadStatusUploadedIssuer.fromJson(Map<String, dynamic> json) {
    final uploadedAt = json['uploaded_at'] as String?;
    return UploadStatusUploadedIssuer(
      code: json['code'] as String,
      displayName: json['display_name'] as String,
      statementId: json['statement_id'] as int,
      uploadedAt: uploadedAt == null ? null : DateTime.parse(uploadedAt),
    );
  }
}

class UploadStatus {
  const UploadStatus({
    required this.year,
    required this.month,
    required this.expectedIssuers,
    required this.uploaded,
    required this.missing,
  });

  final int year;
  final int month;
  final List<UploadStatusIssuer> expectedIssuers;
  final List<UploadStatusUploadedIssuer> uploaded;
  final List<UploadStatusIssuer> missing;

  factory UploadStatus.fromJson(Map<String, dynamic> json) {
    List<T> parseList<T>(
      Object? raw,
      T Function(Map<String, dynamic> json) fromJson,
    ) {
      final items = raw as List<dynamic>? ?? <dynamic>[];
      return items
          .map((item) => fromJson(item as Map<String, dynamic>))
          .toList();
    }

    return UploadStatus(
      year: json['year'] as int,
      month: json['month'] as int,
      expectedIssuers: parseList(json['expected_issuers'], UploadStatusIssuer.fromJson),
      uploaded: parseList(json['uploaded'], UploadStatusUploadedIssuer.fromJson),
      missing: parseList(json['missing'], UploadStatusIssuer.fromJson),
    );
  }
}
