import json
import unittest
from unittest.mock import Mock, patch

from service.assistant import NO_EVIDENCE, AgentError, answer_question, retrieve_trade_notes
from service.customs import TradeDataError, build_comparison, parse_observation


XML = b"""<response><header><resultCode>00</resultCode></header><body><items>
<item><year>2025.10</year><statCd>US</statCd><hsCd>330499</hsCd><expDlr>120000</expDlr></item>
</items></body></response>"""


def tool_call(name, arguments):
    return {"type": "function_call", "name": name, "arguments": json.dumps(arguments)}


def generated_answer(source):
    data = {"claims": [{"text": "기여도는 기준 기간 총액을 분모로 계산합니다.", "source_ids": [source]}]}
    return {"output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(data)}]}]}


RETRIEVAL_CASES = {
    "FOB와 CIF는 어떤 기준이야?": "valuation-basis",
    "HS 품목 코드는 무엇인가요?": "coverage-and-hs",
    "잠정 통계는 언제 갱신돼?": "revisions",
    "성장률 기여도의 분모가 뭐야?": "contribution",
    "샘플의 기타 시장은 어떻게 정의돼?": "sample-method",
    "코스맥스 기업 실적과 수요를 어떻게 해석하지?": "interpretation",
    "수출 금액기준이 뭐야?": "valuation-basis",
    "수출액은 어떤 기준이야?": "valuation-basis",
    "ＨＳ가 뭐야?": "coverage-and-hs",
    "전월자료를 언제 올려?": "revisions",
    "퍼센트 포인트는 뭐야?": "contribution",
    "시험 점수는 어떻게 계산해?": None,
    "신발을 고르는 데 어떤 기준이 좋아?": None,
    "MATHS 시험이 어려워": None,
    "동영상 수정 방법 알려줘": None,
}


class CustomsTests(unittest.TestCase):
    def test_parse_exact_month_partner_and_code(self):
        self.assertEqual(parse_observation(XML, "2025-10", "US", "330499"), 120_000)
        with self.assertRaises(TradeDataError) as missing:
            parse_observation(XML, "2025-10", "CN", "330499")
        self.assertEqual(missing.exception.status, 404)
        self.assertEqual(parse_observation(XML.replace(b"120000", b"0"), "2025-10", "US", "330499"), 0)

    def test_customs_rejects_failed_status_invalid_amount_and_duplicates(self):
        broken = (XML.replace(b">00<", b">30<"), XML.replace(b"120000", b"-"),
                  XML.replace(b"</items>", XML[XML.index(b"<item>"):XML.index(b"</items>")] + b"</items>"))
        for payload in broken:
            with self.subTest(payload=payload):
                with self.assertRaises(TradeDataError) as error:
                    parse_observation(payload, "2025-10", "US", "330499")
                self.assertEqual(error.exception.status, 502)

    @patch.dict("os.environ", {"KCS_SERVICE_KEY": "test-only"})
    @patch("service.customs.fetch_observation", side_effect=[100, 200, 160, 180])
    def test_live_scope_uses_only_selected_partners_in_denominator(self, fetch):
        result = build_comparison("customs", "2025-10", "2026-10", ["US", "JP"], "330499")
        self.assertEqual(fetch.call_count, 4)
        self.assertEqual((result["base_usd"], result["target_usd"]), (300, 340))
        self.assertAlmostEqual(result["rows"][0]["contribution_pp"], 20)
        self.assertIn("US, JP", result["coverage"])


class AssistantTests(unittest.TestCase):
    def test_retrieval_evaluation(self):
        for question, expected in RETRIEVAL_CASES.items():
            with self.subTest(question=question):
                notes = retrieve_trade_notes(question)
                self.assertEqual(notes[0]["id"] if notes else None, expected)

    def test_keyless_pipeline_reconciles_numbers_and_citations(self):
        result = answer_question("수출 성장률 기여도 분모는?", lambda: build_comparison("sample", "2024", "2025"))
        self.assertEqual(result["mode"], "evidence")
        self.assertEqual(result["comparison"]["change_usd"], 1_240_258_000)
        self.assertIn("get_trade_comparison", result["tools"])
        self.assertEqual(result["claims"][0]["source_ids"], ["contribution"])
        self.assertEqual(result["retrieval"], {"query": "수출 성장률 기여도 분모는?", "note_ids": ["contribution"]})
        self.assertEqual(answer_question("운동화 끈 묶기")["message"], NO_EVIDENCE)
        unknown = answer_question("왜 하늘은 파란색이야?")
        self.assertEqual(unknown["message"], NO_EVIDENCE)
        self.assertEqual(unknown["retrieval"]["note_ids"], [])

    def test_agent_executes_tools_then_sends_validated_evidence(self):
        selection = {"output": [tool_call("retrieve_trade_notes", {"query": "성장률 기여도"}),
                                tool_call("get_trade_comparison", {})]}
        call = Mock(side_effect=[selection, generated_answer("contribution")])
        result = answer_question("수출 변화와 기여도 분모는?", lambda: build_comparison("sample", "2024", "2025"), True, call)
        self.assertEqual(call.call_count, 2)
        evidence = json.loads(call.call_args_list[1].args[0]["input"])
        self.assertEqual(evidence["comparison"]["change_usd"], 1_240_258_000)
        self.assertEqual(result["claims"][0]["source_ids"], ["contribution"])
        self.assertEqual(result["mode"], "agent")
        self.assertEqual(result["retrieval"], {"query": "성장률 기여도", "note_ids": ["contribution"]})

    def test_comparison_only_agent_has_no_document_search(self):
        selection = {"output": [tool_call("get_trade_comparison", {})]}
        call = Mock(side_effect=[selection, generated_answer("trade-data")])
        result = answer_question("수출은 얼마나 변했어?", lambda: build_comparison("sample", "2024", "2025"), True, call)
        self.assertIsNone(result["retrieval"])
        self.assertEqual([source["id"] for source in result["sources"]], ["trade-data"])

    def test_invalid_citations_and_tool_arguments_are_rejected(self):
        selection = {"output": [tool_call("retrieve_trade_notes", {"query": "기여도"})]}
        with self.assertRaises(AgentError):
            answer_question("기여도", use_model=True, call=Mock(side_effect=[selection, generated_answer("unknown")]))
        wrong_scope = {"output": [tool_call("get_trade_comparison", {"target": "2030"})]}
        comparison = Mock()
        with self.assertRaises(AgentError):
            answer_question("수출액", comparison, True, Mock(return_value=wrong_scope))
        comparison.assert_not_called()


if __name__ == "__main__":
    unittest.main()
