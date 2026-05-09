class StatementItem {
  StatementItem({
    required this.id,
    required this.usedAt,
    required this.shopName,
    required this.amount,
    this.cardHolder,
    this.categoryId,
    this.classifiedBy,
    required this.source,
  });

  final int id;
  final DateTime usedAt;
  final String shopName;
  final int amount;
  final String? cardHolder;
  final int? categoryId;
  final String? classifiedBy;
  final String source;

  factory StatementItem.fromJson(Map<String, dynamic> json) {
    return StatementItem(
      id: json['id'] as int,
      usedAt: DateTime.parse(json['used_at'] as String),
      shopName: json['shop_name'] as String,
      amount: json['amount'] as int,
      cardHolder: json['card_holder'] as String?,
      categoryId: json['category_id'] as int?,
      classifiedBy: json['classified_by'] as String?,
      source: json['source'] as String? ?? 'csv',
    );
  }
}
