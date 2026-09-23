-- KARTASPB raw OSM staging transport. Permanent tables are managed by Alembic;
-- these underscore-prefixed work tables are merged and removed by the Python CLI.

local node_table = osm2pgsql.define_node_table('_osm_nodes', {
    { column = 'tags', type = 'jsonb', not_null = true },
    { column = 'geom', type = 'point', projection = 4326 },
}, { schema = 'staging' })

local way_table = osm2pgsql.define_way_table('_osm_ways', {
    { column = 'tags', type = 'jsonb', not_null = true },
    { column = 'geom', type = 'geometry', projection = 4326 },
}, { schema = 'staging' })

local relation_table = osm2pgsql.define_relation_table('_osm_relations', {
    { column = 'tags', type = 'jsonb', not_null = true },
}, { schema = 'staging' })

local member_table = osm2pgsql.define_table({
    name = '_osm_relation_members',
    schema = 'staging',
    columns = {
        { column = 'relation_id', type = 'int8', not_null = true },
        { column = 'sequence', type = 'int4', not_null = true },
        { column = 'member_type', type = 'text', not_null = true },
        { column = 'member_id', type = 'int8', not_null = true },
        { column = 'role', type = 'text', not_null = true },
    },
})

local member_types = { n = 'node', w = 'way', r = 'relation' }

-- Untagged nodes are geometry vertices used internally by osm2pgsql. Keeping
-- millions of them as standalone rows would add no future category signal.
local area_keys = {
    amenity = true,
    building = true,
    landuse = true,
    leisure = true,
    natural = true,
    place = true,
    shop = true,
    tourism = true,
}

local function is_area(tags)
    if tags.area == 'yes' then
        return true
    end
    if tags.area == 'no' then
        return false
    end
    for key, _ in pairs(area_keys) do
        if tags[key] ~= nil then
            return true
        end
    end
    return false
end

-- osm2pgsql 1.x only sends tagged ways through process_way in stage 1.
-- Mark every relation-member way for stage 2 so untagged multipolygon,
-- boundary, and route linework is retained in raw staging as well.
function osm2pgsql.select_relation_members(relation)
    return { ways = osm2pgsql.way_member_ids(relation) }
end

function osm2pgsql.process_node(object)
    if next(object.tags) == nil then
        return
    end

    node_table:insert({
        tags = object.tags,
        geom = object:as_point(),
    })
end

function osm2pgsql.process_way(object)
    local geometry
    if object.is_closed and is_area(object.tags) then
        geometry = object:as_polygon()
    else
        geometry = object:as_linestring()
    end

    way_table:insert({
        tags = object.tags,
        geom = geometry,
    })
end

function osm2pgsql.process_relation(object)
    relation_table:insert({ tags = object.tags })

    for sequence, member in ipairs(object.members) do
        member_table:insert({
            relation_id = object.id,
            sequence = sequence - 1,
            member_type = member_types[member.type],
            member_id = member.ref,
            role = member.role or '',
        })
    end
end
