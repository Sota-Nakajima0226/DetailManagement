class StatementItem {
  StatementItem({
    required this.id,
    required this.usedAt,
    required this.shopName,
    required this.amount,
    this.cardHolder,
    this.categoryId,
    this.classifiedBy,
    this.aiConfidence,
    this.needsAiReview = false,
    required this.source,
    this.cardIssuerCode,
    this.cardIssuerName,
  });

  final int id;
  final DateTime usedAt;
  final String shopName;
  final int amount;
  final String? cardHolder;
  final int? categoryId;
  final String? classifiedBy;
  final double? aiConfidence;
  final bool needsAiReview;
  final String source;
  final String? cardIssuerCode;
  final String? cardIssuerName;

  factory StatementItem.fromJson(Map<String, dynamic> json) {
    return StatementItem(
      id: json['id'] as int,
      usedAt: DateTime.parse(json['used_at'] as String),
      shopName: json['shop_name'] as String,
      amount: json['amount'] as int,
      cardHolder: json['card_holder'] as String?,
      categoryId: json['category_id'] as int?,
      classifiedBy: json['classified_by'] as String?,
      aiConfidence: (json['ai_confidence'] as num?)?.toDouble(),
      needsAiReview: json['needs_ai_review'] as bool? ?? false,
      source: json['source'] as String? ?? 'csv',
      cardIssuerCode: json['card_issuer_code'] as String?,
      cardIssuerName: json['card_issuer_name'] as String?,
    );
  }
}
