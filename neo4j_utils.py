from neo4j import GraphDatabase

def query_neo4j(driver, query, parameters=None):
    with driver.session() as session:
        result = session.run(query, parameters)
        return [record.data() for record in result]
