class DetectIssuerCandidate {
  const DetectIssuerCandidate({
    required this.code,
    required this.displayName,
  });

  final String code;
  final String displayName;

  factory DetectIssuerCandidate.fromJson(Map<String, dynamic> json) {
    return DetectIssuerCandidate(
      code: json['code'] as String,
      displayName: json['display_name'] as String,
    );
  }
}

class DetectIssuerResult {
  const DetectIssuerResult({
    this.detectedCode,
    this.detectedDisplayName,
    this.confidence,
    required this.candidates,
  });

  final String? detectedCode;
  final String? detectedDisplayName;
  final String? confidence;
  final List<DetectIssuerCandidate> candidates;

  factory DetectIssuerResult.fromJson(Map<String, dynamic> json) {
    final rawCandidates = json['candidates'] as List<dynamic>? ?? <dynamic>[];
    return DetectIssuerResult(
      detectedCode: json['detected_code'] as String?,
      detectedDisplayName: json['detected_display_name'] as String?,
      confidence: json['confidence'] as String?,
      candidates: rawCandidates
          .map(
            (item) => DetectIssuerCandidate.fromJson(item as Map<String, dynamic>),
          )
          .toList(),
    );
  }
}
