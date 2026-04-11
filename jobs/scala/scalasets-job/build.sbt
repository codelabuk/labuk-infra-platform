
import scala.language.postfixOps

name := "Word Count"
organization := "org.codelabuk"
version := "0.2"

scalaVersion := "2.12.18"

libraryDependencies ++= Seq("org.apache.spark" %% "spark-sql" % "3.5.1" % "provided",
  "com.typesafe" % "config" % "1.4.2"
)

assembly / assemblyJarName := "word-abt.jar"

assembly / assemblyMergeStrategy := {
  case PathList("META-INF", xs @ _*) => MergeStrategy.discard
  case "application.conf"  => MergeStrategy.concat
  case "reference.conf" => MergeStrategy.concat
  case x =>
    val old = (assembly / assemblyMergeStrategy).value
    old(x)
}

