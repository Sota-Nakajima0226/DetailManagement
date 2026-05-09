class UploadResult {
  UploadResult({
    required this.statementId,
    required this.insertedCount,
    required this.unclassifiedCount,
    required this.errorCount,
  });

  final int statementId;
  final int insertedCount;
  final int unclassifiedCount;
  final int errorCount;

  factory UploadResult.fromJson(Map<String, dynamic> json) {
    return UploadResult(
      statementId: json['statement_id'] as int,
      insertedCount: json['inserted_count'] as int? ?? 0,
      unclassifiedCount: json['unclassified_count'] as int? ?? 0,
      errorCount: json['error_count'] as int? ?? 0,
    );
  }
}
