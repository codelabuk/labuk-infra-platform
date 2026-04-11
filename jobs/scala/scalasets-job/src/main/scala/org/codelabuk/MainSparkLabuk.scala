package org.codelabuk

import com.typesafe.config.ConfigFactory
import org.apache.spark.sql.SparkSession

object MainSparkLabuk {

  def main(args: Array[String]): Unit = {
    val config = ConfigFactory.load()
    val appName = config.getString("app.name")
    val inputPath = config.getString("app.file.inputPath")
    val spark = SparkSession.builder().appName(appName).getOrCreate()

    val df = spark.read.option("header","true")
      .csv(inputPath)
    df.printSchema()
    df.show(10)
    val logicalRDDplan = df.queryExecution.analyzed
    logicalRDDplan.printSchema()
  }

}
