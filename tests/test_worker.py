import logging
import unittest
from unittest import mock
from betfairlightweight import BetfairError

from flumine import worker


class BackgroundWorkerTest(unittest.TestCase):
    def setUp(self):
        self.mock_function = mock.Mock()
        self.mock_flumine = mock.Mock()
        self.worker = worker.BackgroundWorker(
            self.mock_flumine,
            self.mock_function,
            123,
            (1, 2),
            {"hello": "world"},
            5,
            {1: 2},
        )

    def test_init(self):
        self.assertEqual(self.worker.interval, 123)
        self.assertEqual(self.worker.function, self.mock_function)
        self.assertEqual(self.worker.flumine, self.mock_flumine)
        self.assertEqual(self.worker.func_args, (1, 2))
        self.assertEqual(self.worker.func_kwargs, {"hello": "world"})
        self.assertEqual(self.worker.start_delay, 5)
        self.assertEqual(self.worker.context, {1: 2})

    # def test_run(self):
    #     self.worker.run()


class WorkersTest(unittest.TestCase):
    def setUp(self) -> None:
        logging.disable(logging.CRITICAL)

    def test_keep_alive(self):
        mock_context = mock.Mock()
        mock_flumine = mock.Mock()
        mock_flumine.client.betting_client.session_token = None
        worker.keep_alive(mock_context, mock_flumine)
        mock_flumine.client.login.assert_called_with()

        mock_flumine.client.betting_client.session_token = 1
        mock_flumine.client.betting_client.session_expired = True
        worker.keep_alive(mock_context, mock_flumine)
        mock_flumine.client.keep_alive.assert_called_with()

    def test_keep_alive_failure(self):
        mock_context = mock.Mock()
        mock_flumine = mock.Mock()
        mock_flumine.client.betting_client.session_token = None
        mock_response = mock.Mock()
        mock_response.status = "FAILURE"
        mock_flumine.client.betting_client.keep_alive.return_value = mock_response
        worker.keep_alive(mock_context, mock_flumine)
        mock_flumine.client.login.assert_called_with()

    def test_keep_alive_error(self):
        mock_context = mock.Mock()
        mock_flumine = mock.Mock()
        mock_flumine.client.betting_client.session_token = None
        mock_flumine.client.betting_client.keep_alive.side_effect = BetfairError
        worker.keep_alive(mock_context, mock_flumine)
        mock_flumine.client.login.assert_called_with()

    def test_keep_alive_ka_error(self):
        mock_context = mock.Mock()
        mock_flumine = mock.Mock()
        mock_flumine.client.betting_client.session_token = 1
        mock_flumine.client.betting_client.session_expired = True
        mock_flumine.client.betting_client.keep_alive.side_effect = BetfairError
        worker.keep_alive(mock_context, mock_flumine)
        mock_flumine.client.keep_alive.assert_called_with()

    @mock.patch("flumine.worker.events")
    def test_poll_market_catalogue(self, mock_events):
        mock_context = mock.Mock()
        mock_flumine = mock.Mock()
        mock_flumine.markets.markets = {"1.234": None, "5.678": None}

        worker.poll_market_catalogue(mock_context, mock_flumine)
        mock_flumine.client.betting_client.betting.list_market_catalogue.assert_called_with(
            filter={"marketIds": list(mock_flumine.markets.markets.keys())},
            market_projection=[
                "COMPETITION",
                "EVENT",
                "EVENT_TYPE",
                "RUNNER_DESCRIPTION",
                "RUNNER_METADATA",
                "MARKET_START_TIME",
                "MARKET_DESCRIPTION",
            ],
            max_results=100,
        )
        mock_flumine.handler_queue.put.assert_called_with(
            mock_events.MarketCatalogueEvent()
        )

    @mock.patch("flumine.worker.events")
    def test_poll_account_balance(self, mock_events):
        mock_context = mock.Mock()
        mock_flumine = mock.Mock()
        mock_flumine.client.account_funds = {1: 2}
        worker.poll_account_balance(mock_context, mock_flumine)
        mock_flumine.client.update_account_details.assert_called_with()
        mock_flumine.log_control.assert_called_with(
            mock_events.BalanceEvent(mock_flumine.client.account_funds)
        )

    # @mock.patch("flumine.worker._get_cleared_market")
    # @mock.patch("flumine.worker._get_cleared_orders")
    # def test_poll_cleared_orders(self, mock__get_cleared_orders, mock__get_cleared_market):
    #     mock_flumine = mock.Mock()
    #     mock_client = mock.Mock()
    #
    #     worker.poll_cleared_orders(mock_flumine, mock_client)
    #

    @mock.patch("flumine.worker.config")
    @mock.patch("flumine.worker.events")
    def test__get_cleared_orders(self, mock_events, mock_config):
        mock_flumine = mock.Mock()
        mock_betting_client = mock.Mock()
        mock_cleared_orders = mock.Mock()
        mock_cleared_orders.orders = []
        mock_cleared_orders.more_available = False
        mock_betting_client.betting.list_cleared_orders.return_value = (
            mock_cleared_orders
        )

        self.assertTrue(
            worker._get_cleared_orders(mock_flumine, mock_betting_client, "1.23")
        )
        mock_betting_client.betting.list_cleared_orders.assert_called_with(
            bet_status="SETTLED",
            market_ids=["1.23"],
            from_record=0,
            customer_strategy_refs=[mock_config.hostname],
        )
        mock_flumine.log_control.assert_called_with(mock_events.ClearedOrdersEvent())
        mock_flumine.handler_queue.put.assert_called_with(
            mock_events.ClearedOrdersEvent()
        )

    @mock.patch("flumine.worker.config")
    @mock.patch("flumine.worker.events")
    def test__get_cleared_orders_error(self, mock_events, mock_config):
        mock_flumine = mock.Mock()
        mock_betting_client = mock.Mock()
        mock_betting_client.betting.list_cleared_orders.side_effect = BetfairError
        self.assertFalse(
            worker._get_cleared_orders(mock_flumine, mock_betting_client, "1.23")
        )
        mock_betting_client.betting.list_cleared_orders.assert_called_with(
            bet_status="SETTLED",
            market_ids=["1.23"],
            from_record=0,
            customer_strategy_refs=[mock_config.hostname],
        )

    @mock.patch("flumine.worker.config")
    @mock.patch("flumine.worker.events")
    def test__get_cleared_market(self, mock_events, mock_config):
        mock_flumine = mock.Mock()
        mock_betting_client = mock.Mock()
        mock_cleared_markets = mock.Mock()
        mock_cleared_markets.orders = [1]
        mock_betting_client.betting.list_cleared_orders.return_value = (
            mock_cleared_markets
        )
        self.assertTrue(
            worker._get_cleared_market(mock_flumine, mock_betting_client, "1.23")
        )
        mock_betting_client.betting.list_cleared_orders.assert_called_with(
            bet_status="SETTLED",
            market_ids=["1.23"],
            group_by="MARKET",
            customer_strategy_refs=[mock_config.hostname],
        )
        mock_flumine.log_control.assert_called_with(mock_events.ClearedMarketsEvent())
        mock_flumine.handler_queue.put.assert_called_with(
            mock_events.ClearedMarketsEvent()
        )

    @mock.patch("flumine.worker.config")
    def test__get_cleared_market_no_orders(self, mock_config):
        mock_flumine = mock.Mock()
        mock_betting_client = mock.Mock()
        mock_cleared_markets = mock.Mock()
        mock_cleared_markets.orders = []
        mock_betting_client.betting.list_cleared_orders.return_value = (
            mock_cleared_markets
        )
        self.assertFalse(
            worker._get_cleared_market(mock_flumine, mock_betting_client, "1.23")
        )
        mock_betting_client.betting.list_cleared_orders.assert_called_with(
            bet_status="SETTLED",
            market_ids=["1.23"],
            group_by="MARKET",
            customer_strategy_refs=[mock_config.hostname],
        )

    @mock.patch("flumine.worker.config")
    @mock.patch("flumine.worker.events")
    def test__get_cleared_market_error(self, mock_events, mock_config):
        mock_flumine = mock.Mock()
        mock_betting_client = mock.Mock()
        mock_betting_client.betting.list_cleared_orders.side_effect = BetfairError
        self.assertFalse(
            worker._get_cleared_market(mock_flumine, mock_betting_client, "1.23")
        )
        mock_betting_client.betting.list_cleared_orders.assert_called_with(
            bet_status="SETTLED",
            market_ids=["1.23"],
            group_by="MARKET",
            customer_strategy_refs=[mock_config.hostname],
        )
