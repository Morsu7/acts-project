from acts.map.road_network import RoadNetwork


def get_config():

    net = RoadNetwork()


    # -------------------------------------------------
    # Intersection
    # -------------------------------------------------

    net.set_intersection_center(
        0,
        (0.0, 0.0)
    )


    net.add_port(10,0,(15,-25))           # single car
    net.add_port(20,0,(0,0))            # multiple cars
    net.add_port(30,0,(-15,-15))        # destination for both cars


    # -------------------------------------------------
    # External nodes
    # -------------------------------------------------

    net.add_port(100,1,(50,-25))        # single car entry
    net.add_port(200,2,(-20,0))         # loop entry
    net.add_port(300,3,(-40,-40))     # far loop node


    # -------------------------------------------------
    # External roads
    # -------------------------------------------------

    net.add_road_edge(30,300)
    net.add_road_edge(300,200)
    net.add_road_edge(200,20)

    net.add_road_edge(100,10)
    net.add_road_edge(30,100)


    # -------------------------------------------------
    # Intersection movements
    # -------------------------------------------------

    net.add_turn_edge(10,30,"turn")
    net.add_turn_edge(20,30,"turn")

    net.set_intersection_phases(0, {
        "tl_10_dir0": 1,  # single car
        "tl_20_dir0": 2,  # multiple car
    })

    net.compile_metadata()

    vehicle_spawns = []

    multiple_cycle = [
        200,
        20,
        30,
        300
    ]

    single_cycle = [
        100,
        10,
        30
    ]


    for i in range(30):
        vehicle_spawns.append(
            (
                f"north_car_{i}",
                200,
                multiple_cycle * 1000 + [400]
            )
        )


    # East single car
    vehicle_spawns.append(("east_waiting_car", 100, single_cycle*1000 + [400]))

    return net, vehicle_spawns