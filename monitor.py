from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet
from ryu.lib import hub


class MonitorSwitch(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(MonitorSwitch, self).__init__(*args, **kwargs)

        # Stores MAC address to port mapping per switch (learning switch behavior)
        self.mac_to_port = {}

        # Stores active datapaths (connected switches)
        self.datapaths = {}

        # Start background thread for periodic monitoring
        self.monitor_thread = hub.spawn(self._monitor)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):

        # Called when a switch connects to the controller
        datapath = ev.msg.datapath
        self.datapaths[datapath.id] = datapath

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Table-miss rule: send unknown packets to controller
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions):

        # Utility function to install flow rules in switch
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                               match=match, instructions=inst)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):

        # Handles incoming packets sent to controller (Packet-In events)
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        dpid = datapath.id

        # Initialize MAC table for this switch if not present
        self.mac_to_port.setdefault(dpid, {})

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        dst = eth.dst
        src = eth.src
        in_port = msg.match['in_port']

        # Learn source MAC address and associated port
        self.mac_to_port[dpid][src] = in_port

        # Decide output port based on destination MAC
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD  # Flood if destination unknown

        actions = [parser.OFPActionOutput(out_port)]

        # Install flow rule for known destinations (avoid future Packet-In)
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst)
            self.add_flow(datapath, 1, match, actions)

        # Prepare packet-out message to forward packet
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(datapath=datapath,
                                 buffer_id=msg.buffer_id,
                                 in_port=in_port,
                                 actions=actions,
                                 data=data)

        datapath.send_msg(out)

    def _monitor(self):

        # Background loop that periodically requests port statistics
        while True:
            for dp in self.datapaths.values():
                self.request_stats(dp)

            # Sleep for 2 seconds between monitoring cycles
            hub.sleep(2)

    def request_stats(self, datapath):

        # Send request to switch for port statistics
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def port_stats_reply_handler(self, ev):

        # Handles response containing port statistics from switch
        print("\n--- Port Stats ---")

        for stat in ev.msg.body:
            # Print RX/TX bytes per port (network utilization)
            print(f"Port {stat.port_no} RX={stat.rx_bytes} TX={stat.tx_bytes}")
