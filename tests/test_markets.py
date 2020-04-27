import unittest
import datetime
from unittest import mock

from flumine.markets.markets import Markets
from flumine.markets.market import Market


class MarketsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.markets = Markets()

    def test_init(self):
        self.assertEqual(self.markets._markets, {})

    def test_add_market(self):
        mock_market = mock.Mock()
        self.markets.add_market("1.1", mock_market)
        self.assertEqual(self.markets._markets, {"1.1": mock_market})

    def test_add_market_reopen(self):
        mock_market = mock.Mock()
        self.markets._markets = {"1.1": mock_market}
        self.markets.add_market("1.1", mock_market)

        self.assertEqual(self.markets._markets, {"1.1": mock_market})
        mock_market.open_market.assert_called_with()

    def test_close_market(self):
        mock_market = mock.Mock()
        self.markets._markets = {"1.1": mock_market}
        self.markets.close_market("1.1")
        mock_market.close_market.assert_called_with()

    def test_get_order(self):
        mock_market = mock.Mock()
        mock_market.closed = False
        mock_market.blotter = {"test": 12}
        self.markets._markets = {"1.1": mock_market}

        self.assertEqual(self.markets.get_order("1.1", "test"), 12)
        self.assertIsNone(self.markets.get_order("1.2", "test"))

    def test_markets(self):
        self.assertEqual(self.markets.markets, {})
        mock_market = mock.Mock()
        mock_market_two = mock.Mock()
        self.markets._markets = {"1.1": mock_market, "2.1": mock_market_two}
        self.assertEqual(
            self.markets.markets, {"1.1": mock_market, "2.1": mock_market_two}
        )

    def test_open_market_ids(self):
        self.assertEqual(self.markets.open_market_ids, [])
        mock_market = mock.Mock()
        mock_market.closed = False
        mock_market_two = mock.Mock()
        mock_market_two.closed = True
        self.markets._markets = {"1.1": mock_market, "2.1": mock_market_two}
        self.assertEqual(self.markets.open_market_ids, [mock_market.market_id])

    def test_live_orders(self):
        self.assertFalse(self.markets.live_orders)
        mock_market = mock.Mock()
        mock_market.closed = False
        mock_market.blotter.live_orders = True
        self.markets._markets = {"1.234": mock_market}
        self.assertTrue(self.markets.live_orders)

    def test_iter(self):
        self.assertEqual(len([i for i in self.markets]), 0)

    def test_len(self):
        self.assertEqual(len(self.markets), 0)


class MarketTest(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_market_book = mock.Mock()
        self.market = Market("1.234", self.mock_market_book)

    def test_init(self):
        self.assertEqual(self.market.market_id, "1.234")
        self.assertEqual(self.market.market_book, self.mock_market_book)
        self.assertFalse(self.market.closed)

    def test_call(self):
        mock_market_book = mock.Mock()
        self.market(mock_market_book)

        self.assertEqual(self.market.market_book, mock_market_book)

    def test_open_market(self):
        self.market.open_market()
        self.assertFalse(self.market.closed)

    def test_close_market(self):
        self.market.close_market()
        self.assertTrue(self.market.closed)

    def test_place_order(self):
        mock_order = mock.Mock()
        mock_order.id = "123"
        self.market.place_order(mock_order)
        mock_order.place.assert_called_with()
        self.assertEqual(self.market.blotter.pending_place, [mock_order])

    def test_place_order_retry(self):
        mock_order = mock.Mock()
        self.market.blotter._orders = {mock_order.id: mock_order}
        self.market.place_order(mock_order)
        self.assertEqual(self.market.blotter.pending_place, [])

    def test_cancel_order(self):
        mock_blotter = mock.Mock()
        mock_blotter.pending_cancel = []
        self.market.blotter = mock_blotter
        mock_order = mock.Mock()
        self.market.cancel_order(mock_order, 0.01)
        mock_order.cancel.assert_called_with(0.01)
        self.assertEqual(mock_blotter.pending_cancel, [mock_order])

    def test_update_order(self):
        mock_blotter = mock.Mock()
        mock_blotter.pending_update = []
        self.market.blotter = mock_blotter
        mock_order = mock.Mock()
        self.market.update_order(mock_order, "PERSIST")
        mock_order.update.assert_called_with("PERSIST")
        self.assertEqual(mock_blotter.pending_update, [mock_order])

    def test_replace_order(self):
        mock_blotter = mock.Mock()
        mock_blotter.pending_replace = []
        self.market.blotter = mock_blotter
        mock_order = mock.Mock()
        self.market.replace_order(mock_order, 1.01)
        mock_order.replace.assert_called_with(1.01)
        self.assertEqual(mock_blotter.pending_replace, [mock_order])

    def test_seconds_to_start(self):
        mock_market_catalogue = mock.Mock()
        mock_market_catalogue.market_start_time = datetime.datetime.utcfromtimestamp(1)
        self.market.market_catalogue = mock_market_catalogue
        self.assertLess(self.market.seconds_to_start, 0)

    def test_seconds_to_start_market_book(self):
        mock_market_book = mock.Mock()
        mock_market_book.market_definition.market_time = datetime.datetime.utcfromtimestamp(
            1
        )
        self.market.market_book = mock_market_book
        self.assertLess(self.market.seconds_to_start, 0)

    def test_seconds_to_start_none(self):
        self.market.market_book = None
        self.market.market_catalogue = None
        self.assertLess(self.market.seconds_to_start, 0)
