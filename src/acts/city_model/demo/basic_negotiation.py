from acts.map.road_network import RoadNetwork

from acts.map.road_network import Direction, DirectionGroup


def get_config():

    net = RoadNetwork()

    # -------------------------------------------------
    # Single 4-way intersection
    # -------------------------------------------------

    net.set_intersection_center(
        0,
        (0.0, 0.0)
    )

    # Local intersection ports
    net.add_port(10, 0, (0, 15))     # north
    net.add_port(20, 0, (15, 0))     # east
    net.add_port(30, 0, (0, -15))    # south
    net.add_port(40, 0, (-15, 0))    # west


    # External spawn ports

    net.add_port(100, 1, (0, 65))
    net.add_port(200, 2, (65, 0))
    net.add_port(300, 3, (0, -65))
    net.add_port(400, 4, (-65, 0))


    # Roads entering intersection

    net.add_road_edge(
        100,
        10,
        tier="local"
    )

    net.add_road_edge(
        200,
        20,
        tier="local"
    )

    net.add_road_edge(
        300,
        30,
        tier="local"
    )

    net.add_road_edge(
        400,
        40,
        tier="local"
    )


    # -------------------------------------------------
    # Intersection movements
    # -------------------------------------------------

    # north exits
    net.add_turn_edge(10,20,"turn")
    net.add_turn_edge(10,30,"turn")
    net.add_turn_edge(10,40,"turn")

    # east exits
    net.add_turn_edge(20,10,"turn")
    net.add_turn_edge(20,30,"turn")
    net.add_turn_edge(20,40,"turn")

    # south exits
    net.add_turn_edge(30,10,"turn")
    net.add_turn_edge(30,20,"turn")
    net.add_turn_edge(30,40,"turn")

    # west exits
    net.add_turn_edge(40,10,"turn")
    net.add_turn_edge(40,20,"turn")
    net.add_turn_edge(40,30,"turn")


    # -------------------------------------------------
    # One direction group per traffic light
    # -------------------------------------------------

    net.set_intersection_priority_groups(
        0,
        [
            DirectionGroup(directions=[Direction(10, 20), Direction(10, 30), Direction(10, 40)], phase_index=1),
            DirectionGroup(directions=[Direction(20, 10), Direction(20, 30), Direction(20, 40)], phase_index=2),
            DirectionGroup(directions=[Direction(30, 10), Direction(30, 20), Direction(30, 40)], phase_index=1),
            DirectionGroup(directions=[Direction(40, 10), Direction(40, 20), Direction(40, 30)], phase_index=2)
        ]
    )

    net.compile_metadata()


    # -------------------------------------------------
    # Heavy north traffic
    # -------------------------------------------------

    vehicle_spawns = [

        ("north_car_1",100,[100,10,20]),
        ("north_car_2",100,[100,10,30]),
        ("north_car_3",100,[100,10,40]),

        ("east_car_1",200,[200,20,30])
    ]


    return net, vehicle_spawns