class StatementUploadResultItem {
  const StatementUploadResultItem({
    required this.cardIssuerCode,
    required this.statementId,
    required this.insertedCount,
    required this.unclassifiedCount,
    required this.errorCount,
  });

  final String cardIssuerCode;
  final int statementId;
  final int insertedCount;
  final int unclassifiedCount;
  final int errorCount;

  factory StatementUploadResultItem.fromJson(Map<String, dynamic> json) {
    return StatementUploadResultItem(
      cardIssuerCode: json['card_issuer_code'] as String,
      statementId: json['statement_id'] as int,
      insertedCount: json['inserted_count'] as int? ?? 0,
      unclassifiedCount: json['unclassified_count'] as int? ?? 0,
      errorCount: json['error_count'] as int? ?? 0,
    );
  }
}

class StatementUploadBatchResult {
  const StatementUploadBatchResult({required this.results});

  final List<StatementUploadResultItem> results;

  factory StatementUploadBatchResult.fromJson(Map<String, dynamic> json) {
    final raw = json['results'] as List<dynamic>? ?? <dynamic>[];
    return StatementUploadBatchResult(
      results: raw
          .map(
            (item) => StatementUploadResultItem.fromJson(item as Map<String, dynamic>),
          )
          .toList(),
    );
  }
}
