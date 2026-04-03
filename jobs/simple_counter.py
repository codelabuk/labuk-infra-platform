import time

from pyspark.sql import SparkSession

def main():
    print("SPARK SIMPLE COUNTER JOBS")
    print("="* 60)

    spark = (SparkSession.builder
             .appName("SimpleCounter")
             .getOrCreate())
    sc = spark.sparkContext
    sc.setLogLevel("WARN")
    print(f"\n[INFO] Spark Versions:{spark.version}")
    print(f"[INFO] Application Id: {sc.applicationId}")
    print(f"[INFO] Master: {sc.master}")


    start_time = time.time()
    num_elements = 100000
    num_partitions = 10

    print(f"[STEP 1] Creating RDD with Number of elements: {num_elements} across {num_partitions} partitions")
    num_rdd = sc.parallelize(range(1, num_elements), num_partitions)

    print(f"[STEP 2] Computation statistics in parallel ...")
    count = num_rdd.count()
    print(f"- Count : {count:,}")
    average = num_rdd.sum() / count
    print(f"- Average: {average:,.2f}")
    min_val = num_rdd.min()
    max_val = num_rdd.max()
    print(f"- Min : {min_val:,.2f}")
    print(f"- Max : {max_val:,.2f}")

    print("\n[STEP 3] Counting even & odd numbers..")
    even_count = num_rdd.filter(lambda x: x % 2 == 0).count()
    odd_count = num_rdd.filter(lambda x: x % 2 != 0).count()
    print(f"- Even Count : {even_count:,}")
    print(f"- Odd Count : {odd_count:,}")

    print("\n[STEP 4] Creating dataframes & performing aggregation")
    df = spark.createDataFrame([
        (i, i*2,'even' if i%2 ==0 else 'odd' for i in range(1, 101))],
        ['number', 'doubled', 'type'])

    print("\n[INFO] SampleDataFrame")
    df.show(5)

    print('\n[INFO] Aggregation by "type":')
    df.groupBy('type').agg(
        {'number': 'sum',
         'doubled': 'avg'}
    ).show()

    elapsed_time = time.time() - start_time


    print("=" * 60)
    print("SPARK SIMPLE COUNTER JOB COMPLETE")
    print(f"\n[INFO] Job completed in {elapsed_time:.2f} seconds:")

    spark.stop()


if __name__ == "__main__":
    main()
