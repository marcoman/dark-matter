# Build with context = this directory (java/):
#   docker build -t dark-matter-java .
#
FROM eclipse-temurin:21-jdk AS build
WORKDIR /build
COPY mvnw pom.xml ./
COPY .mvn .mvn
COPY src ./src
RUN chmod +x mvnw && ./mvnw -q -DskipTests package

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /build/target/dark-matter-*.jar app.jar
EXPOSE 5000
ENV PORT=5000
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
